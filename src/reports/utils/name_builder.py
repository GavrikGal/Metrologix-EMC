# src/reports/utils/name_builder.py
import os
from src.core.math_models import FrequencyConverter


class NameBuilder:
    @staticmethod
    def build_standard_filename(device_config: dict, f_min_hz: float, f_max_hz: float, extension: str = "") -> str:
        """Генерирует строгое имя файла по ГОСТ стандарту: 'Тип, Модель №SN (Диапазон)'.ext"""
        dev_type = device_config.get('device_type', 'Device')
        short_id = device_config.get('device_short_id', 'Unknown')
        sn = device_config.get('serial_number')
        sn_suffix = f" №{sn}" if sn and str(sn).lower() != 'none' else ""

        base_name = f"{dev_type}, {short_id}{sn_suffix}"
        freq_range_str = FrequencyConverter.format_frequency_range(f_min_hz, f_max_hz)

        filename = f"{base_name} ({freq_range_str}){extension}"

        # Очистка от запрещенных символов файловых систем
        for char in ['*', ':', '"', '<', '>', '|', '?']:
            filename = filename.replace(char, '')
        return filename
