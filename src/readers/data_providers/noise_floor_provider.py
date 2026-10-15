# src/readers/data_providers/noise_floor_provider.py
import os
import logging
import numpy as np
import pandas as pd
from .base_provider import BaseDataProvider
from src.readers.hardware_data_reader import HardwareDataReader
from src.core.data_structures.parameter import Parameter
from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty
from src.core.utils.trace_manipulator import TraceManipulator
from src.core.math_models import FrequencyConverter

logger = logging.getLogger("Metrologix")


class NoiseFloorDataProvider(BaseDataProvider):
    """Провайдер расчета неопределенности от минимального уровня шума по ГОСТ CISPR 16-4-2 Рисунок А.1"""

    # Оцифрованная нелинейная кривая СИСПР для квазипикового детектора
    CISPR_SN_GRID = np.array([
        0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0,
        10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 20.0, 25.0, 30.0
    ])
    CISPR_ERR_GRID = np.array([
        5.2, 5.0, 4.5, 4.0, 3.6, 3.2, 2.8, 2.4, 2.1, 1.8,
        1.6, 1.3, 1.1, 0.9, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.05, 0.0
    ])

    def get_parameter(self) -> Parameter:
        reader_settings = self.config.get('reader_settings', {})
        # Из пришедшего файла Keysight вытягиваем колонку FREQ (3) и квазипик QPD AMPL (5)
        columns_mapping = reader_settings.get('columns_mapping', {'frequency': 3, 'value': 5})

        raw_paths = self.config.get('file_path')
        if not raw_paths:
            raise ValueError("[NoiseFloorProvider] Не задан параметр 'file_path'.")

        # Приводим к единому списку, даже если указан всего один файл строкой
        file_list = [raw_paths] if isinstance(raw_paths, str) else raw_paths

        loaded_segments = []
        src_unit = reader_settings.get('file_frequency_unit', 'Hz')
        ratio = FrequencyConverter.get_ratio(from_unit=src_unit, to_unit='Hz')

        # 1. Считываем каждый файл поддиапазона шумов в отдельный Trace
        for file_name in file_list:
            full_path = os.path.join(self.root_dir, file_name)
            logger.info(f"Парсинг фрагмента поддиапазона шумов: {file_name}")

            df = HardwareDataReader.read_measurement_data(
                file_path=full_path,
                file_format=reader_settings.get('file_format', 'text'),
                data_start_marker=reader_settings.get('data_start_marker', 'DATA'),
                skip_rows=reader_settings.get('skip_rows', 0),
                delimiter=reader_settings.get('delimiter', ',')
            )

            # Вырезаем частоты и децибелы квазипика
            freqs_hz = df[columns_mapping['frequency']].values.astype(float) * ratio
            qpd_values = df[columns_mapping['value']].values.astype(float)

            loaded_segments.append(Trace(freqs_hz, qpd_values))

        # 2. 🌟 ВЫЗОВ МАНИПУЛЯТОРА: Склеиваем все поддиапазоны в одну бесконечную опорную трассу шума прибора
        full_noise_trace = TraceManipulator.join_sequences(loaded_segments)

        # 3. Извлекаем трассу лимитов (нормы) текущей задачи, подброшенную Движком
        task_limit_trace = self.config.get('task_limit_trace')
        if not task_limit_trace:
            raise ValueError("[NoiseFloorProvider] Трасса лимитов задачи не передана в провайдер!")

        # 4. 🌟 СВЕДЕНИЕ СЕТОК: Соединяем сетку объединенного шума и сетку переломных точек лимита задачи
        aligned_noise_trace, aligned_limit_trace = TraceManipulator.concatenate_grids(
            full_noise_trace,
            task_limit_trace
        )

        calculation_grid = aligned_noise_trace.frequencies

        # 5. РАСЧЕТ СООТНОШЕНИЯ СИГНАЛ/ШУМ В КАЖДОЙ ТОЧКЕ ОБЪЕДИНЕННОЙ СЕТКИ
        signal_to_noise_ratio = aligned_limit_trace.values - aligned_noise_trace.values
        signal_to_noise_ratio = np.clip(signal_to_noise_ratio, 0.0, 30.0)

        # 6. ВЫЧИСЛЕНИЕ ПОГРЕШНОСТИ КВАЗИПИКА ПО КРИВОЙ СИСПР
        calculated_error_values = np.interp(signal_to_noise_ratio, self.CISPR_SN_GRID, self.CISPR_ERR_GRID)

        # 7. СИНТЕЗ ПАРАМЕТРА ДЛЯ ДВИЖКА
        final_value_trace = Trace(calculation_grid, np.zeros_like(calculation_grid))

        final_uncertainty_trace = Uncertainty(
            frequencies=calculation_grid,
            values=calculated_error_values,
            distribution_type='rectangular',
            is_symmetric=False,  # 🌟 Указываем, что интервал несимметричный
        )

        logger.info(f"Успешно синтезирован параметр шумов. Точек склейки: {len(calculation_grid)}, "
                    f"Худшая погрешность детектора: {calculated_error_values.max():.2f} дБ")

        return Parameter(final_value_trace, final_uncertainty_trace)
