import os
import glob
import yaml
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from abc import ABC, abstractmethod
from src.readers.universal_csv_reader import UniversalCSVReader
from src.core.math_models import DistributionDecomposition


class BaseDevice(ABC):
    """Абстрактный базовый класс с универсальной логикой загрузки и обработки данных"""

    def __init__(self, device_dir_path: str):
        self.device_dir_path = device_dir_path
        self.config_path = os.path.join(device_dir_path, "device_config.yaml")
        self.config = self.load_config()
        self.name = self.config.get('device_name', 'Unknown Device')

        # Универсальное хранилище обработанных параметров:
        # { 'S21': {'freq': [...], 'value': [...], 'u_standard': [...]}, 'Impedance': ... }
        self.processed_parameters = {}

    def load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Конфигурация прибора отсутствует: {self.config_path}")
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    @abstractmethod
    def process_device_data(self):
        """Каждое устройство вызывает этот метод, но структура вызовов внутри него уникальна"""
        pass

    # =====================================================================
    # УНИВЕРСАЛЬНЫЕ СТРАТЕГИИ ЗАГРУЗКИ ДАННЫХ (ОБЩИЕ ДЛЯ ВСЕХ ДЕВАЙСОВ)
    # =====================================================================

    def _load_as_constant(self, param_name: str, cfg: dict):
        """Параметр задан как фиксированная константа во всем диапазоне"""
        # Генерируем базовую сетку от 100 кГц до 40 ГГц для инициализации
        freqs = np.logspace(5, 10.6, num=500)
        values = np.full_like(freqs, cfg.get('value', 0.0))

        unc_cfg = cfg.get('uncertainty', {})
        raw_unc = np.full_like(freqs, unc_cfg.get('value', 0.0))
        u_std = DistributionDecomposition.to_standard(raw_unc, unc_cfg.get('distribution', 'rectangular'))

        self.processed_parameters[param_name] = {'freq': freqs, 'value': values, 'u_standard': u_std}

    def _load_from_table(self, param_name: str, cfg: dict):
        """Данные загружаются из готовой таблицы паспорта или сертификата калибровки"""
        file_path = os.path.join(self.device_dir_path, cfg.get('file_path'))
        r_set = cfg.get('reader_settings', {})
        mapping = r_set.get('columns_mapping', {'frequency': 0, 'value': 1})

        df = UniversalCSVReader.read_csv_data(
            file_path=file_path,
            skip_rows=r_set.get('skip_rows', 0),
            delimiter=r_set.get('delimiter', ',')
        )

        freqs = df[mapping['frequency']].values
        values = df[mapping['value']].values

        unc_cfg = cfg.get('uncertainty', {})
        if unc_cfg.get('type') == 'constant':
            raw_unc = np.full_like(freqs, unc_cfg.get('value', 0.0))
        else:
            # Если неопределенность лежит в соседней колонке таблицы
            unc_col = mapping.get('uncertainty', 2)
            raw_unc = df[unc_col].values

        u_std = DistributionDecomposition.to_standard(
            raw_unc,
            unc_cfg.get('distribution', 'normal'),
            k_factor=unc_cfg.get('k_factor', 2)
        )

        self.processed_parameters[param_name] = {'freq': freqs, 'value': values, 'u_standard': u_std}

    def _normalize_and_align_grids(self, freqs_a: np.ndarray, data_a: dict,
                                   freqs_b: np.ndarray, data_b: dict) -> tuple[np.ndarray, dict, dict]:
        """
        Вспомогательный метод: сравнивает две частотные сетки,
        выбирает наиболее подробную в качестве целевой и интерполирует редкие данные.

        data_a и data_b — словари вида {'mean': массив, 'std': массив}
        """
        if len(freqs_a) == len(freqs_b):
            target_freqs = freqs_a
            aligned_a = data_a
            aligned_b = data_b
        elif len(freqs_a) > len(freqs_b):
            # Сетка А подробнее или равна Б. Берем ее за основу.
            target_freqs = freqs_a
            aligned_a = data_a

            aligned_b = {
                'mean': interp1d(freqs_b, data_b['mean'], kind='linear', fill_value="extrapolate")(target_freqs),
                'std': interp1d(freqs_b, data_b['std'], kind='linear', fill_value="extrapolate")(target_freqs)
            }
        else:
            # Сетка Б подробнее. Интерполируем данные А под нее.
            target_freqs = freqs_b
            aligned_b = data_b

            aligned_a = {
                'mean': interp1d(freqs_a, data_a['mean'], kind='linear', fill_value="extrapolate")(target_freqs),
                'std': interp1d(freqs_a, data_a['std'], kind='linear', fill_value="extrapolate")(target_freqs)
            }

        return target_freqs, aligned_a, aligned_b

    def _collect_file_paths(self, input_path) -> list:
        """
        Универсальный сборщик путей.
        Понимает: одиночный файл, список файлов или путь к папке.
        """
        if isinstance(input_path, list):
            # Если передан список, преобразуем относительные пути в абсолютные
            return [os.path.join(self.device_dir_path, f) for f in input_path]

        full_path = os.path.join(self.device_dir_path, input_path)

        if os.path.isdir(full_path):
            # Если это папка — забираем ВСЕ файлы .csv внутри нее
            # Сортировка важна, чтобы файлы шли последовательно, хотя concat потом все равно отсортирует по частоте
            found_files = sorted(glob.glob(os.path.join(full_path, "*.csv")))
            if not found_files:
                raise FileNotFoundError(f"[{self.name}] В папке {full_path} не найдено CSV-файлов!")
            return found_files
        elif os.path.isfile(full_path):
            # Если это одиночный файл
            return [full_path]
        else:
            raise FileNotFoundError(f"[{self.name}] Путь не найден: {full_path}")

    def _read_and_merge_system_files(self, input_config, r_set, trace_cols) -> pd.DataFrame:
        """Вспомогательный метод: собирает пути, читает файлы через Reader и склеивает их"""
        file_paths = self._collect_file_paths(input_config)

        dfs = []
        for path in file_paths:
            df_part = UniversalCSVReader.read_csv_data(
                file_path=path,
                data_start_marker=r_set.get('data_start_marker'),
                delimiter=r_set.get('delimiter', ','),
                use_columns=trace_cols,
                nan_values=r_set.get('nan_values')
            )
            dfs.append(df_part)

        # Склеиваем все считанные файлы (декады) и сортируем по частоте (колонка 0)
        return pd.concat(dfs, ignore_index=True).sort_values(0)

    def _calculate_via_substitution(self, param_name: str, cfg: dict):
        """Модернизированный метод замещения с поддержкой папок и списков файлов"""
        r_set = cfg.get('reader_settings', {})
        trace_cols = r_set.get('use_columns', )

        # Колонки для расчета средних (все, кроме колонки частоты, которая идет под индексом 0)
        only_traces = [c for c in trace_cols if c != 0]
        n_traces = len(only_traces)

        # Автоматически собираем и читаем данные из папок или списков
        df_sys1 = self._read_and_merge_system_files(cfg['system1_baseline'], r_set, trace_cols)
        df_sys2 = self._read_and_merge_system_files(cfg['system2_with_cable'], r_set, trace_cols)

        # 💡 ИСПРАВЛЕНИЕ: Вытаскиваем строго первую колонку (индекс 0) как одномерный вектор частот
        # Свойство .values от pandas Series гарантированно возвращает одномерный массив (1D array)
        freqs_1 = df_sys1[0].values
        freqs_2 = df_sys2[0].values

        # Собираем расчетные метрики (среднее и СКО) по трассам измерений
        data_1 = {
            'mean': df_sys1[only_traces].mean(axis=1).values,
            'std': df_sys1[only_traces].std(axis=1, ddof=1).values
        }
        data_2 = {
            'mean': df_sys2[only_traces].mean(axis=1).values,
            'std': df_sys2[only_traces].std(axis=1, ddof=1).values
        }

        # Выравниваем частотные сетки (метод принимает одномерные массивы freqs_1 и freqs_2)
        target_freqs, aligned_1, aligned_2 = self._normalize_and_align_grids(freqs_1, data_1, freqs_2, data_2)

        # Физический расчет затухания и неопределенности типа А
        calculated_values = aligned_2['mean'] - aligned_1['mean']
        sem_1 = aligned_1['std'] / np.sqrt(n_traces)
        sem_2 = aligned_2['std'] / np.sqrt(n_traces)
        u_type_a = np.sqrt(sem_1 ** 2 + sem_2 ** 2)

        # Сохраняем в кэш девайса
        self.processed_parameters[param_name] = {
            'freq': target_freqs,
            'value': calculated_values,
            'u_standard': u_type_a
        }
        print(f"[{self.name}] Успешный расчет '{param_name}'. Итоговый рабочий диапазон железа: "
              f"{target_freqs.min() / 1e6:.2f} - {target_freqs.max() / 1e9:.2f} ГГц ({len(target_freqs)} точек).")

    def get_parameter_vector(self, parameter_name: str, target_frequencies: np.ndarray) -> tuple[
        np.ndarray, np.ndarray]:
        """Универсальный интерфейс для внешнего Движка с экстраполяцией и контролем границ"""
        if parameter_name not in self.processed_parameters:
            raise ValueError(f"[{self.name}] Параметр '{parameter_name}' не найден.")

        data = self.processed_parameters[parameter_name]

        # Контролируем, не ушли ли мы в область экстраполяции (предсказания)
        if target_frequencies.max() > data['freq'].max() or target_frequencies.min() < data['freq'].min():
            print(f"[Метрологическое предупреждение]: Внимание! Запрошенные задачей частоты выходят за "
                  f"пределы физических измерений прибора '{self.name}' "
                  f"({data['freq'].min() / 1e6:.1f} МГц - {data['freq'].max() / 1e9:.1f} ГГц). "
                  f"Включен режим математического предсказания (экстраполяции)!")

        # Возвращаем интерполяцию/экстраполяцию
        val_interp = interp1d(data['freq'], data['value'], kind='linear', fill_value="extrapolate")(target_frequencies)
        u_interp = interp1d(data['freq'], data['u_standard'], kind='linear', fill_value="extrapolate")(
            target_frequencies)

        return val_interp, u_interp
