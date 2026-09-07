import os
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
        if len(freqs_a) >= len(freqs_b):
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

    def _calculate_via_substitution(self, param_name: str, cfg: dict):
        """Универсальный метод замещения с автоматическим выравниванием сеток частот"""
        r_set = cfg.get('reader_settings', {})
        trace_cols = r_set.get('use_columns', [1, 2, 3])  # колонки измерительных трасс (без частоты)
        n_traces = len(trace_cols)

        sys1_file = os.path.join(self.device_dir_path, cfg['system1_baseline'])
        sys2_file = os.path.join(self.device_dir_path, cfg['system2_with_cable'])

        # Читаем обе системы через маркер начала данных
        df_sys1 = UniversalCSVReader.read_csv_data(sys1_file, data_start_marker=r_set.get('data_start_marker'))
        df_sys2 = UniversalCSVReader.read_csv_data(sys2_file, data_start_marker=r_set.get('data_start_marker'))

        freqs_1 = df_sys1[0].values
        freqs_2 = df_sys2[0].values

        # Собираем первичные расчетные метрики (среднее и СКО) для каждой системы локально
        data_1 = {
            'mean': df_sys1[trace_cols].mean(axis=1).values,
            'std': df_sys1[trace_cols].std(axis=1, ddof=1).values
        }
        data_2 = {
            'mean': df_sys2[trace_cols].mean(axis=1).values,
            'std': df_sys2[trace_cols].std(axis=1, ddof=1).values
        }

        # Выравниваем сетки (метод сам поймет, какой файл длиннее, и интерполирует короткий)
        target_freqs, aligned_1, aligned_2 = self._normalize_and_align_grids(freqs_1, data_1, freqs_2, data_2)

        # Универсальный расчет разности (Система 2 - Система 1)
        calculated_values = aligned_2['mean'] - aligned_1['mean']

        # Расчет стандартной неопределенности типа А (SEM = STD / sqrt(n))
        sem_1 = aligned_1['std'] / np.sqrt(n_traces)
        sem_2 = aligned_2['std'] / np.sqrt(n_traces)
        u_type_a = np.sqrt(sem_1 ** 2 + sem_2 ** 2)

        # Сохраняем в универсальную базу
        self.processed_parameters[param_name] = {
            'freq': target_freqs,
            'value': calculated_values,
            'u_standard': u_type_a
        }
        print(
            f"[{self.name}] Параметр '{param_name}' успешно рассчитан (размер целевой сетки: {len(target_freqs)} точек).")

    def get_parameter_vector(self, parameter_name: str, target_frequencies: np.ndarray) -> tuple[
        np.ndarray, np.ndarray]:
        """Универсальный интерфейс для внешнего Движка"""
        if parameter_name not in self.processed_parameters:
            raise ValueError(f"[{self.name}] Параметр '{parameter_name}' не найден в обработанных данных.")

        data = self.processed_parameters[parameter_name]

        val_interp = interp1d(data['freq'], data['value'], kind='linear', fill_value="extrapolate")(target_frequencies)
        u_interp = interp1d(data['freq'], data['u_standard'], kind='linear', fill_value="extrapolate")(
            target_frequencies)

        return val_interp, u_interp
