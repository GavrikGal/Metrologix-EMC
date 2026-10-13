# src/readers/data_providers/calculated_trace_difference_provider.py
import os
import numpy as np
import pandas as pd
from .base_provider import BaseDataProvider
from src.readers.hardware_data_reader import HardwareDataReader
from src.core.data_structures.parameter import Parameter
from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty
from src.core.utils.trace_manipulator import TraceManipulator


class CalculatedTraceDifferenceProvider(BaseDataProvider):
    """Провайдер параметров, вычисляемых как разность двух трасс (Система 2 - Система 1)"""

    def get_parameter(self) -> Parameter:
        reader_settings = self.config.get('reader_settings', {})
        columns_mapping = reader_settings.get('use_columns', )  # [Частота, Трасса1, Трасса2...]

        # 1. Загружаем сырые данные Системы 1 и Системы 2 из файлов (метод ниже больше не заглушка!)
        system1_param = self._load_system_raw_parameter(self.config['system1_baseline'], reader_settings,
                                                        columns_mapping)
        system2_param = self._load_system_raw_parameter(self.config['system2_with_cable'], reader_settings,
                                                        columns_mapping)

        # 2. Склеиваем сетки частот и выравниваем ТРАССЫ ЗНАЧЕНИЙ через наш манипулятор
        aligned_trace1, aligned_trace2 = TraceManipulator.concatenate_grids(
            system1_param.value_trace,
            system2_param.value_trace
        )

        # 3. Склеиваем сетки частот и выравниваем ТРАССЫ НЕОПРЕДЕЛЕННОСТЕЙ
        aligned_unc1, aligned_unc2 = TraceManipulator.concatenate_grids(
            system1_param.uncertainty_trace,
            system2_param.uncertainty_trace
        )

        # 4. Физический расчет разности систем на единой объединенной сетке
        calculation_grid = aligned_trace1.frequencies
        calculated_values = aligned_trace2.values - aligned_trace1.values
        calculated_u_type_a = np.sqrt(aligned_unc1.values ** 2 + aligned_unc2.values ** 2)

        # 5. Упаковка в финальный Parameter
        value_trace = Trace(calculation_grid, calculated_values)
        uncertainty_trace = Uncertainty(calculation_grid, calculated_u_type_a, distribution_type='normal', k_factor=1.0)

        final_parameter = Parameter(value_trace, uncertainty_trace)

        # Передаем оригинальные многомерные матрицы для отчетов протокола
        final_parameter.sys1_traces = system1_param.sys1_traces
        final_parameter.sys2_traces = system2_param.sys2_traces

        return final_parameter

    def _load_system_raw_parameter(self, paths_config, reader_settings, columns_mapping) -> Parameter:
        """Внутренний метод: последовательно считывает файлы системы, применяет offset и считает СКО"""
        only_traces_columns = [col for col in columns_mapping if col != 0]
        number_of_traces = len(only_traces_columns)

        # Подготовка списка файлов и их индивидуальных смещений дБ (offset)
        file_items = []
        if isinstance(paths_config, str):
            file_items.append({'path': paths_config, 'offset_db': 0.0})
        else:
            for item in paths_config:
                if isinstance(item, str):
                    file_items.append({'path': item, 'offset_db': 0.0})
                elif isinstance(item, dict):
                    file_items.append({'path': item.get('path'), 'offset_db': float(item.get('offset_db', 0.0))})

        # Построчно считываем и склеиваем файлы (например, разбитые по декадам)
        data_frames = []
        for item in file_items:
            full_path = os.path.join(self.root_dir, item['path'])
            df_part = HardwareDataReader.read_measurement_data(
                file_path=full_path,
                file_format=reader_settings.get('file_format', 'text'),
                data_start_marker=reader_settings.get('data_start_marker'),
                skip_rows=reader_settings.get('skip_rows', 0),
                delimiter=reader_settings.get('delimiter', ','),
                use_columns=columns_mapping,
                nan_values=reader_settings.get('nan_values')
            )

            # Применяем поправку уровня генератора (offset_db), если она задана в конфиге задачи
            if item['offset_db'] != 0.0:
                df_part[only_traces_columns] = df_part[only_traces_columns] + item['offset_db']
            data_frames.append(df_part)

        # Объединяем файлы, сортируем по частоте (0-я колонка) и чистим дубликаты на стыках декад
        df_merged = pd.concat(data_frames, ignore_index=True).sort_values(0)
        df_clean = df_merged.drop_duplicates(subset=[0], keep='last')

        # Извлекаем финальный массив частот (переводим ось в Герцы)
        raw_frequencies = df_clean[0].values.astype(float)

        # 🌟 МАТЕМАТИЧЕСКИЙ РАСЧЕТ СРЕДНЕГО И СКО (Неопределенность типа А)
        # mean(axis=1) считает среднюю трассу затухания
        mean_values = df_clean[only_traces_columns].mean(axis=1).values
        # std(axis=1, ddof=1) считает экспериментальное СКО для n-трасс
        std_deviations = df_clean[only_traces_columns].std(axis=1, ddof=1).values

        # Стандартная неопределенность среднего значения (u = s / sqrt(n))
        u_type_a_values = std_deviations / np.sqrt(number_of_traces)

        # Собираем промежуточный Parameter
        value_trace = Trace(raw_frequencies, mean_values)
        uncertainty_trace = Uncertainty(raw_frequencies, u_type_a_values, distribution_type='normal', k_factor=1.0)

        parameter = Parameter(value_trace, uncertainty_trace)

        # Кэшируем сырую многомерную матрицу отсчетов для будущего рендерера таблиц
        parameter.sys1_traces = df_clean[only_traces_columns].values
        parameter.sys2_traces = df_clean[only_traces_columns].values

        return parameter
