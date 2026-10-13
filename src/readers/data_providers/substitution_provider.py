# src/readers/data_providers/substitution_provider.py
import os
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from .base_provider import BaseDataProvider
from src.readers.hardware_data_reader import HardwareDataReader
from src.core.data_structures.parameter import Parameter
from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty


class SubstitutionDataProvider_deprecated(BaseDataProvider):
    """Стратегия сложного расчета затухания и неопределенности типа А методом замещения"""

    def get_parameter(self) -> Parameter:
        r_set = self.config.get('reader_settings', {})
        trace_cols = r_set.get('use_columns', [0, 1, 2, 3])  # Пример дефолтных колонок
        only_traces = [c for c in trace_cols if c != 0]
        n_traces = len(only_traces)

        # 1. Читаем и склеиваем файлы декад для обеих систем
        df_sys1 = self._read_and_merge_system_files(self.config['system1_baseline'], r_set, trace_cols)
        df_sys2 = self._read_and_merge_system_files(self.config['system2_with_cable'], r_set, trace_cols)

        freqs_1 = df_sys1[0].values
        freqs_2 = df_sys2[0].values

        data_1 = {
            'mean': df_sys1[only_traces].mean(axis=1).values,
            'std': df_sys1[only_traces].std(axis=1, ddof=1).values,
        }
        data_2 = {
            'mean': df_sys2[only_traces].mean(axis=1).values,
            'std': df_sys2[only_traces].std(axis=1, ddof=1).values,
        }

        # 2. Метрологическое выравнивание частотных сеток
        target_freqs, aligned_1, aligned_2 = self._align_grids(freqs_1, data_1, freqs_2, data_2)

        # 3. Физический расчет затухания (S21) и неопределенности типа А
        calculated_values = aligned_2['mean'] - aligned_1['mean']
        sem_1 = aligned_1['std'] / np.sqrt(n_traces)
        sem_2 = aligned_2['std'] / np.sqrt(n_traces)
        u_type_a = np.sqrt(sem_1 ** 2 + sem_2 ** 2)

        # 4. Упаковка в ленивые структуры данных
        value_trace = Trace(target_freqs, calculated_values)
        # Тип А по GUM/СИСПР всегда нормальный с k=1 (стандартная неопределенность)
        uncertainty_trace = Uncertainty(
            frequencies=target_freqs,
            values=u_type_a,
            distribution_type='normal',
            k_factor=1.0
        )

        parameter = Parameter(value_trace, uncertainty_trace)

        # Кэшируем сырые матрицы замерных трасс прямо в динамические атрибуты параметра для ProtocolTableExporter
        parameter.sys1_traces = df_sys1[only_traces].values
        parameter.sys2_traces = df_sys2[only_traces].values

        return parameter

    def _read_and_merge_system_files(self, input_config, r_set, trace_cols) -> pd.DataFrame:
        """Служебный метод: склеивает файлы декад и учитывает индивидуальные смещения дБ"""
        only_traces = [c for c in trace_cols if c != 0]
        file_items = []

        if isinstance(input_config, str):
            file_items.append({'path': input_config, 'offset_db': 0.0})
        else:
            for item in input_config:
                if isinstance(item, str):
                    file_items.append({'path': item, 'offset_db': 0.0})
                elif isinstance(item, dict):
                    file_items.append({'path': item.get('path'), 'offset_db': float(item.get('offset_db', 0.0))})

        dfs = []
        for item in file_items:
            full_path = os.path.join(self.root_dir, item['path'])

            # 🌟 ИСПРАВЛЕНИЕ: Передаем ВСЕ метрологические фильтры, как в вашем исходном коде
            df_part = HardwareDataReader.read_measurement_data(
                file_path=full_path,
                file_format=r_set.get('file_format', 'text'),
                data_start_marker=r_set.get('data_start_marker'),  # <--- ВОЗВРАЩАЕМ МАРКЕР "DATA"
                skip_rows=r_set.get('skip_rows', 0),
                delimiter=r_set.get('delimiter', ','),
                use_columns=trace_cols,
                nan_values=r_set.get('nan_values')
            )

            if item['offset_db'] != 0.0:
                df_part[only_traces] = df_part[only_traces] + item['offset_db']
            dfs.append(df_part)

        # Склеиваем, сортируем по частоте (колонка 0) и удаляем дубликаты
        df_merged = pd.concat(dfs, ignore_index=True).sort_values(0)
        return df_merged.drop_duplicates(subset=[0], keep='last')

    def _align_grids(self, freqs_a: np.ndarray, data_a: dict, freqs_b: np.ndarray, data_b: dict):
        """Интерполяция под общую сетку частот"""
        min_freq = max(freqs_a.min(), freqs_b.min())
        max_freq = min(freqs_a.max(), freqs_b.max())

        target_freqs = freqs_a[(freqs_a >= min_freq) & (freqs_a <= max_freq)] if len(freqs_a) >= len(freqs_b) else \
        freqs_b[(freqs_b >= min_freq) & (freqs_b <= max_freq)]

        aligned_a = {
            'mean': interp1d(freqs_a, data_a['mean'], kind='linear')(target_freqs),
            'std': interp1d(freqs_a, data_a['std'], kind='linear')(target_freqs)
        }
        aligned_b = {
            'mean': interp1d(freqs_b, data_b['mean'], kind='linear')(target_freqs),
            'std': interp1d(freqs_b, data_b['std'], kind='linear')(target_freqs)
        }
        return target_freqs, aligned_a, aligned_b
