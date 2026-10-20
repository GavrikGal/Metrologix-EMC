# src/readers/data_providers/calculated_trace_difference_provider.py
import os
import numpy as np
import pandas as pd
import logging
from .base_provider import BaseDataProvider
from src.readers.hardware_data_reader import HardwareDataReader
from src.core.data_structures.parameter import Parameter
from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty
from src.core.utils.trace_manipulator import TraceManipulator

logger = logging.getLogger("Metrologix")


class CalculatedTraceDifferenceProvider(BaseDataProvider):
    """Провайдер параметров, вычисляемых как разность двух трасс (Система 2 - Система 1)"""

    def get_parameter(self) -> Parameter:
        reader_settings = self.config.get('reader_settings', {})
        columns_mapping = reader_settings.get('use_columns', )

        system1_param = self._load_system_raw_parameter(self.config['system1_baseline'], reader_settings, columns_mapping)
        system2_param = self._load_system_raw_parameter(self.config['system2_with_cable'], reader_settings, columns_mapping)

        # Вычитаем один объект из другого оператором!
        # Иммутабельный оператор '-' вернет новый Parameter, сохранив исходные системы целыми
        final_parameter = system2_param - system1_param

        # Задаем динамическое имя параметра из YAML-конфигурации прибора
        final_parameter.name = self.config.get('parameter_system_name', 'S21')

        # Переносим сырые многомерные матрицы для отчетов протокола
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
        # df_clean = df_merged.drop_duplicates(subset=[0], keep='last')
        df_clean = df_merged

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

        parameter = Parameter(name=self.config.get('parameter_system_name', 'S21'),
                              value_trace=value_trace, uncertainty_trace=uncertainty_trace)

        # Кэшируем сырую многомерную матрицу отсчетов для будущего рендерера таблиц
        parameter.sys1_traces = df_clean[only_traces_columns].values
        parameter.sys2_traces = df_clean[only_traces_columns].values

        return parameter
