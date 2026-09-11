# Файл: src/hardware/process/measurement_process.py
from src.hardware.base_device import BaseDevice


class MeasurementProcess(BaseDevice):
    """Класс-плагин для учета погрешностей показаний, оператора и нестабильности процесса"""

    def process_device_data(self):
        """Пробегается по параметрам конфига и инициализирует константы или таблицы оператора"""
        params_cfg = self.config.get('parameters', {})

        for param_name, target_cfg in params_cfg.items():
            src_type = target_cfg.get('source_type')

            if src_type == 'constant':
                self._load_as_constant(param_name, target_cfg)
            elif src_type == 'table':
                self._load_from_table(param_name, target_cfg)
