from src.hardware.base_device import BaseDevice


class LISN(BaseDevice):
    """Класс-плагин для эквивалентов сети питания"""

    def process_device_data(self):
        """Стратегии загрузки таблиц поверки"""
        params_cfg = self.config.get('parameters', {})

        for param_name, target_cfg in params_cfg.items():
            src_type = target_cfg.get('source_type')

            if src_type == 'table':
                self._load_from_table(param_name, target_cfg)
            elif src_type == 'constant':
                self._load_as_constant(param_name, target_cfg)
