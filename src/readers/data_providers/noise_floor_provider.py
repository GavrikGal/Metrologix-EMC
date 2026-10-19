# src/readers/data_providers/noise_floor_provider.py
import os
import logging
import numpy as np
from .base_provider import BaseDataProvider
from src.readers.hardware_data_reader import HardwareDataReader
from src.core.data_structures.parameter import Parameter
from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty
from src.core.utils.trace_manipulator import TraceManipulator
from src.core.math_models import FrequencyConverter


logger = logging.getLogger("Metrologix")


class NoiseFloorDataProvider(BaseDataProvider):
    """Провайдер расчета неопределенности от минимального уровня шума по ГОСТ CISPR 16-4-2"""

    def get_parameter(self) -> Parameter:
        reader_settings = self.config.get('reader_settings', {})
        columns_mapping = reader_settings.get('columns_mapping', {'frequency': 3, 'value': 5})

        raw_paths = self.config.get('file_path')
        if not raw_paths:
            raise ValueError("[NoiseFloorProvider] Не задан параметр 'file_path'.")

        file_list = [raw_paths] if isinstance(raw_paths, str) else raw_paths
        loaded_segments = []

        src_unit = reader_settings.get('file_frequency_unit', 'Hz')
        ratio = FrequencyConverter.get_ratio(from_unit=src_unit, to_unit='Hz')

        # 1. Загружаем и склеиваем куски файлов поддиапазонов шумов прибора
        for file_name in file_list:
            full_path = os.path.join(self.root_dir, file_name)
            df = HardwareDataReader.read_measurement_data(
                file_path=full_path, file_format=reader_settings.get('file_format', 'text'),
                data_start_marker=reader_settings.get('data_start_marker', 'DATA'),
                skip_rows=int(reader_settings.get('skip_rows', 0)), delimiter=reader_settings.get('delimiter', ',')
            )
            freqs_hz = df[columns_mapping['frequency']].values.astype(float) * ratio
            qpd_values = df[columns_mapping['value']].values.astype(float)

            loaded_segments.append(Trace(freqs_hz, qpd_values))


        full_noise_trace = TraceManipulator.join_sequences(loaded_segments)

        noise = Parameter('Noise', full_noise_trace)

        # 2. Извлекаем трассу лимитов задачи
        task_limit_trace = self.config.get('task_limit_trace')

        # 3. Извлекаем динамическую кривую СИСПР из конфига провайдера
        cispr_graph_trace = self.config.get('cispr_graph_trace')
        if not task_limit_trace or not cispr_graph_trace:
            raise ValueError("[NoiseFloorProvider] Критические трассы СИСПР или лимитов отсутствуют в конфигурации.")

        # 5. Вычисляем соотношение Сигнал/Шум
        signal_to_noise_ratio = task_limit_trace - noise

        # 🌟 6. ИНТЕРПОЛЯЦИЯ НА ЛЕТУ СИЛАМИ САМОГО ОБЪЕКТА TRACE ГРАФИКА
        # Мы просто просим объект cispr_graph_trace выдать значения погрешностей
        # для вычисленных соотношений signal_to_noise_ratio
        calculated_error_values = cispr_graph_trace.value_trace.get_values_for_frequencies(
            signal_to_noise_ratio.value_trace.values
        )

        # 7. Финальный синтез метрологических объектов
        final_value_trace = Trace.create_zeros_like(signal_to_noise_ratio.value_trace)
        final_uncertainty_trace = Uncertainty(
            frequencies=signal_to_noise_ratio.value_trace.frequencies,
            values=calculated_error_values,
            distribution_type='rectangular',
            is_symmetric=False
        )

        logger.info(f"Успешно синтезирован параметр шумов. Точек склейки: {len(calculated_error_values)}, "
                    f"Худшая погрешность детектора: {calculated_error_values.max():.2f} дБ")

        return Parameter('Noise_Floor', final_value_trace, final_uncertainty_trace)
