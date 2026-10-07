# Файл: src/reports/template_exporter.py
import os
from jinja2 import Template


class TemplateExporter:
    """Универсальный обработчик текстовых шаблонов для экспорта данных в приборы"""

    @staticmethod
    def export_correction(template_path: str, output_path: str,
                          frequencies: list, values: list,
                          freq_convert_ratio: float, sign_multiplier: float,
                          meta_params: dict):
        """Загружает Jinja2-шаблон, подготавливает данные и генерирует файл коррекции"""
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"[TemplateExporter] Шаблон не найден: {template_path}")

        # 1. Честный математический пересчет векторов без потери знаков
        processed_freqs = [f * freq_convert_ratio for f in frequencies]
        processed_values = [v * sign_multiplier for v in values]

        data_points = list(zip(processed_freqs, processed_values))

        # 2. Рендеринг шаблона Jinja2
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()

        template = Template(template_content)
        rendered_content = template.render(data_points=data_points, **meta_params)

        # 3. Сохранение результата
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(rendered_content)

        print(f"[TemplateExporter] Создан файл: {os.path.basename(output_path)}")
