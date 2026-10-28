# src/reports/renderers/table_renderer.py
import os
import numpy as np
import logging

from src.core.data_structures import uncertainty
from src.core.data_structures.parameter import Parameter
from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty
from src.core.utils import logger
from src.reports.base_renderer import BaseRenderer
from src.reports.protocol_table_exporter import ProtocolTableExporter
from src.reports.utils.name_builder import NameBuilder

logger = logging.getLogger("Metrologix")


class TableRenderer(BaseRenderer):
    """Компонент выборки реальных физических точек и генерации CSV-таблиц протокола"""

    def render(self, output_dir: str, device_config: dict, param_name: str,
               parameter: Parameter, f_min_hz: float, f_max_hz: float, target_pts_count: int, sub_unit: str):

        # 🌟 ИСПРАВЛЕНИЕ: Запрашиваем метрологически чистый срез реальных точек у самой Трассы
        # raw_freqs, raw_values = parameter.value_trace.get_raw_slice(f_min_hz, f_max_hz)

        # Получение трассы с N максимальных измеренных неопределенностей
        final_values, raw_uncertainty = parameter.get_raw_max_data_in_frequency_range(f_min_hz, f_max_hz,
                                                                                      max_by='value',
                                                                                      points_count=target_pts_count)
        # Частоты N максимальных измеренных неопределенностей
        final_freqs = final_values.frequencies

        # Алгоритм прореживания выборки до целевого количества (table_points_count)
        # if len(raw_freqs) <= target_pts_count:
        #     chosen_indices = np.arange(len(raw_freqs))
        # else:
        #     ideal_grid = np.linspace(f_min_hz, f_max_hz, num=target_pts_count)
        #     chosen_indices = []
        #     for ideal_f in ideal_grid:
        #         closest_idx = np.argmin(np.abs(raw_freqs - ideal_f))
        #         if closest_idx not in chosen_indices:
        #             chosen_indices.append(closest_idx)
        #     chosen_indices = np.array(chosen_indices)

        # logger.debug(f'{chosen_indices=}')

        # max_value_freq, max_value = parameter.uncertainty_trace.get_max_uncertainties_in_range(f_min_hz, f_max_hz)
        # logger.debug(f'{max_value_freq=}')
        # logger.debug(f'{np.where(raw_freqs==max_value_freq)=}')
        # logger.debug(f'{max_value=}')

        # chosen_indices = np.append(chosen_indices, np.argmin(np.abs(raw_freqs - max_value_freq)))
        # logger.debug(f'{chosen_indices=}')

        # final_freqs = raw_freqs[chosen_indices]
        # logger.debug(f'{final_freqs=}')


        # final_values = raw_values[chosen_indices]

        # Получение значений, где неопределенность максимальна
        # final_values, _ = parameter.get_values_for_frequencies(final_freqs)

        # Сборка структур многомерных замещений
        if parameter.raw_data is not None:
            sys1 = parameter.raw_data[0]
            sys2 = parameter.raw_data[1]
        else:
            sys1 = None
            sys2 = None

        # sys1 = parameter.__dict__.get('sys1_traces')
        # sys2 = parameter.__dict__.get('sys2_traces')
        # unc1 = parameter.__dict__.get('sys1_unc')
        # unc2 = parameter.__dict__.get('sys2_unc')

        _, final_u_std = parameter.get_values_for_frequencies(final_freqs)

        if sys1 is not None and sys2 is not None:
            sys1_name = sys1.name
            sys2_name = sys2.name
            sys1_slice = sys1.get_block_of_raw_data_for_frequencies(final_freqs)
            sys2_slice = sys2.get_block_of_raw_data_for_frequencies(final_freqs)
            sys1_value, sys1_unc = sys1.get_values_for_frequencies(final_freqs)
            sys2_value, sys2_unc = sys2.get_values_for_frequencies(final_freqs)
            sys1_mean = sys1_value
            sys1_std = sys1_unc
            sys2_mean = sys2_value
            sys2_std = sys2_unc
        else:
            sys1_name = 'System 1'
            sys2_name = 'System 2'
            # sys1_slice = np.zeros((len(final_freqs), 1))
            # sys2_slice = np.zeros((len(final_freqs), 1))
            sys1_slice = [Trace.create_zeros_like(raw_uncertainty).values]
            sys2_slice = [Trace.create_zeros_like(raw_uncertainty).values]
            sys1_mean, sys2_mean = final_values.values, final_values.values
            sys1_std, sys2_std = final_u_std, final_u_std

        raw_slice = {
            'freq_hz': final_freqs,
            'values_db': final_values,
            # Если неопределенности нет — подставляем массив нулей для стабильности CSV
            'raw_uncertainty_db': final_u_std if final_u_std is not None else np.zeros_like(final_freqs),
            'sys1_name': sys1_name, 'sys2_name': sys2_name,
            'sys1_traces': sys1_slice, 'sys2_traces': sys2_slice,
            'sys1_mean_db': sys1_mean, 'sys2_mean_db': sys2_mean,
            'sys1_std_db': sys1_std, 'sys2_std_db': sys2_std
        }

        filename = NameBuilder.build_standard_filename(device_config, f_min_hz, f_max_hz, param_name=param_name)
        os.makedirs(output_dir, exist_ok=True)
        ProtocolTableExporter.export_raw_slice(output_dir, filename, raw_slice, sub_unit, param_name)
