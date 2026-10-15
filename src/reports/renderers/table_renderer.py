# src/reports/renderers/table_renderer.py
import os
import numpy as np

from src.reports.base_renderer import BaseRenderer
from src.reports.protocol_table_exporter import ProtocolTableExporter
from src.reports.utils.name_builder import NameBuilder


class TableRenderer(BaseRenderer):
    """Компонент выборки реальных физических точек и генерации CSV-таблиц протокола"""

    def render(self, output_dir: str, device_config: dict, param_name: str,
               parameter, f_min_hz: float, f_max_hz: float, target_pts_count: int, sub_unit: str):

        # 🌟 ИСПРАВЛЕНИЕ: Запрашиваем метрологически чистый срез реальных точек у самой Трассы
        raw_freqs, raw_values = parameter.value_trace.get_raw_slice(f_min_hz, f_max_hz)

        # Алгоритм прореживания выборки до целевого количества (table_points_count)
        if len(raw_freqs) <= target_pts_count:
            chosen_indices = np.arange(len(raw_freqs))
        else:
            ideal_grid = np.linspace(f_min_hz, f_max_hz, num=target_pts_count)
            chosen_indices = []
            for ideal_f in ideal_grid:
                closest_idx = np.argmin(np.abs(raw_freqs - ideal_f))
                if closest_idx not in chosen_indices:
                    chosen_indices.append(closest_idx)
            chosen_indices = np.array(chosen_indices)

        final_freqs = raw_freqs[chosen_indices]
        final_values = raw_values[chosen_indices]

        # Сборка структур многомерных замещений
        sys1 = parameter.__dict__.get('sys1_traces')
        sys2 = parameter.__dict__.get('sys2_traces')

        if sys1 is not None and sys2 is not None:
            sys1_slice = sys1[chosen_indices, :]
            sys2_slice = sys2[chosen_indices, :]
            sys1_mean = np.mean(sys1_slice, axis=1)
            sys2_mean = np.mean(sys2_slice, axis=1)
        else:
            sys1_slice = np.zeros((len(final_freqs), 1))
            sys2_slice = np.zeros((len(final_freqs), 1))
            sys1_mean, sys2_mean = final_values, final_values

        raw_slice = {
            'freq_hz': final_freqs,
            'values_db': final_values,
            'raw_uncertainty_db': parameter.uncertainty_trace.get_values_for_frequencies(
                final_freqs) if parameter.uncertainty_trace else np.zeros_like(final_freqs),
            'sys1_traces': sys1_slice, 'sys2_traces': sys2_slice,
            'sys1_mean_db': sys1_mean, 'sys2_mean_db': sys2_mean
        }

        filename = NameBuilder.build_standard_filename(device_config, f_min_hz, f_max_hz)
        os.makedirs(output_dir, exist_ok=True)
        ProtocolTableExporter.export_raw_slice(output_dir, filename, raw_slice, sub_unit, param_name)
