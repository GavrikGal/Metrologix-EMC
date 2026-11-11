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

        system1_param = self._load_system_raw_parameter(self.config['system1_baseline'], reader_settings,
                                                        columns_mapping, parameter_name='baseline')
        system2_param = self._load_system_raw_parameter(self.config['system2_with_cable'], reader_settings,
                                                        columns_mapping, parameter_name='with_cable')

        # Вычитание одного измеренного параметра из другого
        final_parameter = system2_param - system1_param

        # Расчет неопределенности с учетом нелинейности шкалы анализатора и его полосы пропускания
        # 1. ДИНАМИЧЕСКИЙ РАСЧЕТ ТИПА В (Relative Display Scale Fidelity)
        # todo: это надо уметь делать в получая данные от приемника
        attenuation = final_parameter.value_trace.values

        # Перевод значений из дБмкВ в дБм на входе смесителя
        internal_att_db = 10.0
        p1_mixer = system1_param.value_trace.values - 107.0 - internal_att_db
        p2_mixer = system2_param.value_trace.values - 107.0 - internal_att_db
        p_ref = -10.0

        # а) High level term (Примечание e): точный расчет экспоненциальной зависимости.
        # В ВЧ-диапазонах Keysight шаг нормируется относительно 20 дБ (шкала напряжения/амплитуды)
        delta_high_level = 0.015 * np.abs(np.exp((p1_mixer - p_ref) / 8.69) - np.exp((p2_mixer - p_ref) / 8.69))

        # б) Slope term (Примечание g): зависит от модуля разности уровней (затухания)
        delta_slope = 0.0004 * np.abs(attenuation)

        # в) Prefilter term (Примечание h): фиксированный предел для swept режима
        delta_prefilter = 0.005

        # Линейная сумма пределов плоских погрешностей (согласно примечанию d)
        delta_linearity_total = delta_high_level + delta_slope + delta_prefilter

        # Стандартная неопределенность нелинейности (равномерный закон распределения)
        u_linearity_flat = delta_linearity_total

        # г) Instability term (Примечание f): стабильность во времени, задана как 0.0019 dB rms (при измерении
        # в течение минуты)
        u_instability = 0.0019

        # Полная стандартная неопределенность верности шкалы (Fidelity)
        # Складываем квадраты и делим на np.sqrt(3), так как прямоугольное распределение (тип B заявленное изготовителем)
        u_fidelity_total = np.sqrt(u_linearity_flat ** 2 + u_instability ** 2) / np.sqrt(3)

        # 2: Погрешность переключения полосы пропускания (RBW Switching Uncertainty)
        # По паспорту составляет +-0.03 дБ для НЧ, но так как переключений полос нет, то и не учитываем
        # delta_rbw = 0.03
        # u_b_rbw = delta_rbw / np.sqrt(3)

        # 3. СУММАРНАЯ стандартная неопределенность u_c
        # u_c = np.sqrt(final_parameter.uncertainty_trace.values ** 2 + u_fidelity_total ** 2 + u_b_rbw ** 2)
        u_c = np.sqrt(final_parameter.uncertainty_trace.values ** 2 + u_fidelity_total ** 2)
        final_uncertainty_trace = Uncertainty(final_parameter.uncertainty_trace.frequencies,
                                              u_c * 2,
                                              final_parameter.uncertainty_trace.frequencies_units,
                                              final_parameter.uncertainty_trace.values_units,
                                              distribution_type='normal',
                                              k_factor=2.0)
        final_parameter.uncertainty_trace = final_uncertainty_trace

        # final_parameter.uncertainty_trace.values = u_c

        # Задание динамического имени параметра из YAML-конфигурации прибора
        final_parameter.name = self.config.get('parameter_system_name', 'S21')

        # Сохранение исходных измеренных параметров
        final_parameter.raw_data = [system1_param, system2_param]

        # Переносим сырые многомерные матрицы для отчетов протокола
        # todo: В Parameter есть параметр для хранения исходных данных - использовать его
        # final_parameter.sys1_traces = system1_param.sys_raw_traces
        # final_parameter.sys1_unc = system1_param.uncertainty_trace.values
        # final_parameter.sys2_traces = system2_param.sys_raw_traces
        # final_parameter.sys2_unc = system2_param.uncertainty_trace.values

        return final_parameter


    def _load_system_raw_parameter(self, paths_config, reader_settings,
                                   columns_mapping, parameter_name: str) -> Parameter:
        """Внутренний метод: последовательно считывает файлы системы, применяет offset и считает СКО"""
        only_traces_columns = [col for col in columns_mapping if col != 0]
        number_of_traces = len(only_traces_columns)

        # Чтение датафрейма данных из файлов
        df_clean = self._read_raw_data(paths_config, reader_settings, columns_mapping)

        # Извлекаем финальный массив частот (переводим ось в Герцы)
        raw_frequencies = df_clean[0].values.astype(float)
        raw_data = []
        # for trace in df_clean[only_traces_columns].values:
        for trace in only_traces_columns:
            raw_data.append(Trace(raw_frequencies, df_clean[trace].values))



        # 🌟 МАТЕМАТИЧЕСКИЙ РАСЧЕТ СРЕДНЕГО И СКО (Неопределенность типа А)
        # mean(axis=1) считает среднюю трассу затухания
        mean_values = df_clean[only_traces_columns].mean(axis=1).values

        # # Учет неопределенности нелинейности шкалы измерительного прибора
        # # Граничный порог различной нелинейности шкалы
        # floor = -18.0 + 107.01 + 10.0
        # # Неопределенность нелинейности шкалы для каждой измеренной точки
        # u_scale_fidelity = np.where(mean_values >= floor, 0.1, 0.07) # todo: данные из паспорта надо это не жостко вшивать
        # u_scale_fidelity = u_scale_fidelity / np.sqrt(3) # для прямоугольного распределения

        # std(axis=1, ddof=1) считает экспериментальное СКО для n-трасс
        std_deviations = df_clean[only_traces_columns].std(axis=1, ddof=1).values

        # Стандартная неопределенность среднего значения (u = s / sqrt(n))
        u_type_a_values = std_deviations / np.sqrt(number_of_traces)

        # # Сложение через корень неопределенностей
        # u_total = np.sqrt((u_type_a_values) ** 2 + (u_scale_fidelity) ** 2)
        u_total = u_type_a_values

        # Собираем промежуточный Parameter
        value_trace = Trace(raw_frequencies, mean_values)
        uncertainty_trace = Uncertainty(raw_frequencies, u_total, distribution_type='normal', k_factor=1.0)

        parameter = Parameter(name=parameter_name, value_trace=value_trace, uncertainty_trace=uncertainty_trace)

        # Кэшируем сырую многомерную матрицу отсчетов для будущего рендерера таблиц
        # parameter.sys_raw_traces = df_clean[only_traces_columns].values
        parameter.raw_data = raw_data

        return parameter


    def _read_raw_data(self, paths_config, reader_settings, columns_mapping) -> pd.DataFrame:
        only_traces_columns = [col for col in columns_mapping if col != 0]

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
        return df_clean

