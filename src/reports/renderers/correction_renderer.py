# src/reports/renderers/correction_renderer.py
import os
import numpy as np
from src.core.math_models import FrequencyConverter
from src.reports.base_renderer import BaseRenderer
from src.reports.template_exporter import TemplateExporter
from src.reports.utils.name_builder import NameBuilder


class CorrectionRenderer(BaseRenderer):
    """Компонент умной интерполяции сеток и экспорта файлов поправок через Jinja2 шаблоны"""

    def render(self, output_dir: str, device, param_name: str, settings: dict, target_frequencies: np.ndarray):
        parameter = device.processed_parameters[param_name]
        interp_values, _ = parameter.get_aligned_vectors(target_frequencies)

        rules = device.config.get('correction_export_rules', {})
        template_file = rules.get('template_file')
        if not rules or not template_file:
            return

        template_path = os.path.join(device.device_dir_path, template_file)
        target_freq_unit = rules.get('target_freq_unit', 'MHz')

        multiplier = -1.0 if settings.get('invert_sign', False) else 1.0
        freq_ratio = FrequencyConverter.get_ratio(from_unit='Hz', to_unit=target_freq_unit)

        standard_filename = NameBuilder.build_standard_filename(
            device.config,
            target_frequencies.min(),
            target_frequencies.max()
        )

        # 🌟 ИСПРАВЛЕНИЕ: Добавляем индекс, чтобы взять только ".csv", а не весь кортеж
        ext = os.path.splitext(template_file)[1]

        # Собираем итоговое имя файла
        filename = f"{standard_filename}{ext}"

        os.makedirs(output_dir, exist_ok=True)

        TemplateExporter.export_correction(
            template_path=template_path, output_path=os.path.join(output_dir, filename),
            frequencies=target_frequencies.tolist(), values=interp_values.tolist(),
            freq_convert_ratio=freq_ratio, sign_multiplier=multiplier, meta_params=rules.get('template_meta', {})
        )
