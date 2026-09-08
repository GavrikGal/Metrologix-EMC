# Файл: src/hardware/rf_cable/rf_cable.py
from src.hardware.base_device import BaseDevice


class RFCableSystem(BaseDevice):
    """Класс-шаблон для любых кабельных систем и аттенюаторов"""

    def process_device_data(self):
        """
        Просто пробегаемся по параметрам из прочитанного при инициализации конфига
        и запускаем универсальные методы родительского класса BaseDevice.
        """
        params_cfg = self.config.get('parameters', {})

        for param_name, target_cfg in params_cfg.items():
            src_type = target_cfg.get('source_type')

            if src_type == 'constant':
                self._load_as_constant(param_name, target_cfg)

            elif src_type == 'table':
                self._load_from_table(param_name, target_cfg)

            elif src_type == 'calculated_substitution':
                self._calculate_via_substitution(param_name, target_cfg)
