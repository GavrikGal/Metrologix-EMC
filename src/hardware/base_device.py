import os
import glob
import yaml
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from abc import ABC, abstractmethod
# from src.readers.universal_csv_reader import UniversalCSVReader
from src.readers.hardware_data_reader import HardwareDataReader
from src.core.math_models import DistributionDecomposition, FrequencyConverter


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
        """Загружает данные параметра из готовой таблицы поверки (CSV или Excel)"""
        file_path = os.path.join(self.device_dir_path, cfg.get('file_path'))
        r_set = cfg.get('reader_settings', {})
        mapping = cfg.get('columns_mapping', {'frequency': 0, 'value': 1, 'uncertainty': 2})

        df = HardwareDataReader.read_measurement_data(
            file_path=file_path, file_format=r_set.get('file_format', 'text'),
            skip_rows=r_set.get('skip_rows', 0), delimiter=r_set.get('delimiter', ',')
        )

        raw_freqs = df[mapping['frequency']].values.astype(float)
        values = df[mapping['value']].values.astype(float)

        # Конвертируем частоту в системные Герцы
        src_freq_unit = r_set.get('file_frequency_unit', 'Hz')
        ratio = FrequencyConverter.get_ratio(from_unit=src_freq_unit, to_unit='Hz')
        freqs_in_hz = raw_freqs * ratio

        # Забираем исходные настройки распределения
        unc_cfg = cfg.get('uncertainty', {})
        if unc_cfg.get('type') == 'constant':
            raw_unc = np.full_like(freqs_in_hz, unc_cfg.get('value', 0.0))
        else:
            raw_unc = df[mapping['uncertainty']].values.astype(float)

        # 💡 МЕТРОЛОГИЧЕСКОЕ ИЗМЕНЕНИЕ: Сохраняем в кэш СЫРЫЕ (исходные) метрологические параметры распределения
        self.processed_parameters[param_name] = {
            'freq': freqs_in_hz,
            'value': values,
            'raw_uncertainty': raw_unc,  # Исходный массив погрешностей
            'distribution': unc_cfg.get('distribution', 'normal'),  # Исходный закон распределения
            'k_factor': unc_cfg.get('k_factor', 2)  # Исходный коэффициент k
        }
        print(f"[{self.name}] Параметр '{param_name}' успешно зарегистрирован в сыром метрологическом виде.")

    def _normalize_and_align_grids(self, freqs_a: np.ndarray, data_a: dict,
                                   freqs_b: np.ndarray, data_b: dict) -> tuple[np.ndarray, dict, dict]:
        """
        Выравнивает частотные сетки, ограничивая итоговый диапазон строго зоной
        пересечения (intersection), защищая края от разлета неопределенности.
        """
        # Находим строго общий диапазон частот, где данные есть у ОБЕИХ систем
        min_freq = max(freqs_a.min(), freqs_b.min())
        max_freq = min(freqs_a.max(), freqs_b.max())

        # Выбираем, какая сетка подробнее внутри этого общего диапазона
        if len(freqs_a) >= len(freqs_b):
            mask = (freqs_a >= min_freq) & (freqs_a <= max_freq)
            target_freqs = freqs_a[mask]
        else:
            mask = (freqs_b >= min_freq) & (freqs_b <= max_freq)
            target_freqs = freqs_b[mask]

        # Интерполируем строго внутри гарантированных физических границ (bounds_error=True保護)
        # Больше никакой слепой экстраполяции для векторов средних и СКО!
        aligned_a = {
            'mean': interp1d(freqs_a, data_a['mean'], kind='linear', bounds_error=True)(target_freqs),
            'std': interp1d(freqs_a, data_a['std'], kind='linear', bounds_error=True)(target_freqs)
        }

        aligned_b = {
            'mean': interp1d(freqs_b, data_b['mean'], kind='linear', bounds_error=True)(target_freqs),
            'std': interp1d(freqs_b, data_b['std'], kind='linear', bounds_error=True)(target_freqs)
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
        """Служебный метод: читает файлы декад, склеивает их и учитывает индивидуальные смещения дБ"""
        only_traces = [c for c in trace_cols if c != 0]

        if isinstance(input_config, str):
            file_paths = self._collect_file_paths(input_config)
            file_items = [{'path': p, 'offset_db': 0.0} for p in file_paths]
        else:
            file_items = []
            for item in input_config:
                if isinstance(item, str):
                    file_items.append({'path': item, 'offset_db': 0.0})
                elif isinstance(item, dict):
                    file_items.append({'path': item.get('path'), 'offset_db': float(item.get('offset_db', 0.0))})

        dfs = []
        for item in file_items:
            full_path = os.path.join(self.device_dir_path, item['path'])

            # 💡 ЧИСТЫЙ И ОЧЕВИДНЫЙ ВЫЗОВ ДЛЯ СЫРЫХ ЗАМЕРОВ ТРАКТА:
            df_part = HardwareDataReader.read_measurement_data(
                file_path=full_path,
                file_format=r_set.get('file_format', 'text'),
                data_start_marker=r_set.get('data_start_marker'),
                delimiter=r_set.get('delimiter', ','),
                use_columns=trace_cols,
                nan_values=r_set.get('nan_values')
            )

            if item['offset_db'] != 0.0:
                df_part[only_traces] = df_part[only_traces] + item['offset_db']
                print(
                    f"[{self.name}] Применено смещение {item['offset_db']:+.1f} дБ к файлу: {os.path.basename(item['path'])}")

            dfs.append(df_part)

        df_merged = pd.concat(dfs, ignore_index=True).sort_values(0)
        df_merged = df_merged.drop_duplicates(subset=[0], keep='last')
        return df_merged

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
            'raw_uncertainty': u_type_a,
            'distribution': 'normal',
            'k_factor': 1
        }
        print(f"[{self.name}] Успешный расчет '{param_name}'. Итоговый рабочий диапазон железа: "
              f"{target_freqs.min() / 1e6:.2f} - {target_freqs.max() / 1e9:.2f} ГГц ({len(target_freqs)} точек).")

    def get_parameter_vector(self, parameter_name: str, target_frequencies: np.ndarray) -> tuple[
        np.ndarray, np.ndarray]:
        """Универсальный интерфейс для Движка с динамическим расчетом стандартной неопределенности"""
        if parameter_name not in self.processed_parameters:
            raise ValueError(f"[{self.name}] Параметр '{parameter_name}' не найден.")

        data = self.processed_parameters[parameter_name]

        f_min_hardware = data['freq'].min()
        f_max_hardware = data['freq'].max()

        # Защита от ложных округлений float на краях диапазонов
        tolerance_min = f_min_hardware * 0.0001
        tolerance_max = f_max_hardware * 0.0001

        if (target_frequencies.max() > (f_max_hardware + tolerance_max) or
                target_frequencies.min() < (f_min_hardware - tolerance_min)):
            print(f"[Метрологическое предупреждение]: Запрошенные частоты выходят за "
                  f"пределы измерений '{self.name}' ({f_min_hardware / 1e6:.2f} МГц - {f_max_hardware / 1e9:.2f} ГГц). "
                  f"Включен режим экстраполяции!")

        # 1. Интерполируем средние значения физической величины
        val_interp = interp1d(data['freq'], data['value'], kind='linear', fill_value="extrapolate")(target_frequencies)

        # 2. Интерполируем СЫРУЮ неопределенность прибора на целевую сетку частот
        raw_unc_interp = interp1d(data['freq'], data['raw_uncertainty'], kind='linear', fill_value="extrapolate")(
            target_frequencies)

        # 3. 💡 КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Приводим интерполированную сырую неопределенность
        # к стандартной (k=1) в зависимости от сохраненного в объекте закона распределения
        u_std_interp = DistributionDecomposition.to_standard(
            value=raw_unc_interp,
            dist_type=data['distribution'],
            k_factor=data['k_factor']
        )

        return val_interp, u_std_interp

    def get_default_frequencies(self, parameter_name: str) -> np.ndarray:
        """Возвращает оригинальную (дефолтную) ось частот параметра, считанную из файлов прибора"""
        if parameter_name not in self.processed_parameters:
            raise ValueError(f"[{self.name}] Параметр '{parameter_name}' еще не обработан или отсутствует.")
        return self.processed_parameters[parameter_name]['freq']

    def get_max_standard_uncertainty(self, param_name: str, f_min_hz: float, f_max_hz: float) -> dict:
        """
        Находит точку максимальной неопределенности внутри исследуемого диапазона частот
        и возвращает полный метрологический паспорт этой составляющей для таблицы СИСПР.
        """
        if param_name not in self.processed_parameters:
            raise ValueError(f"[{self.name}] Параметр '{param_name}' отсутствует.")

        data = self.processed_parameters[param_name]

        # Строим маску для выделения частот, попавших в диапазон метода задачи
        mask = (data['freq'] >= f_min_hz) & (data['freq'] <= f_max_hz)

        if not np.any(mask):
            # Если точки прибора не попали в диапазон (например, кабель измерялся от 10 МГц, а задача от 150 кГц),
            # берем крайнее ближайшее значение (экстраполяция одной критической точки)
            idx = np.argmin(np.abs(data['freq'] - f_min_hz))
            max_raw_unc = data['raw_uncertainty'][idx]
        else:
            # Находим МАКСИМАЛЬНУЮ сырую неопределенность внутри исследуемого диапазона частот
            max_raw_unc = np.max(data['raw_uncertainty'][mask])

        # Рассчитываем приведенное к стандарту (k=1) значение через наш модуль DistributionDecomposition
        u_std = DistributionDecomposition.to_standard(
            value=max_raw_unc,
            dist_type=data['distribution'],
            k_factor=data['k_factor']
        )

        # Возвращаем полный паспорт строки бюджета СИСПР
        return {
            'raw_value': max_raw_unc,
            'distribution': data['distribution'],
            'k_factor': data['k_factor'],
            'standard_uncertainty': u_std
        }
