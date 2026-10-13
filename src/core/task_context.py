# src/core/task_context.py
import os
import yaml
from src.core.math_models import FrequencyConverter
from src.readers.data_providers.provider_factory import DataProviderFactory


class TaskContext:
    """Контейнер для хранения параметров и конфигурации текущей измерительной задачи"""

    def __init__(self, task_config_path: str, settings: dict, root_dir: str):
        self.root_dir = root_dir
        self.settings = settings  # 🌟 Сохраняем глобальные настройки

        with open(task_config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.task_name = self.config.get('task_name', 'Default_Task')
        self.output_dir = os.path.join(root_dir, "output", self.task_name)

        # Физические границы полосы частот задачи
        b_cfg = self.config.get('budget_range_settings', {})
        self.unit = b_cfg.get('unit', 'Hz')
        self.ratio_to_hz = FrequencyConverter.get_ratio(from_unit=self.unit, to_unit='Hz')
        self.f_min_hz = b_cfg.get('freq_min', 150e3) * self.ratio_to_hz
        self.f_max_hz = b_cfg.get('freq_max', 30e6) * self.ratio_to_hz

        # 🌟 Загружаем лимиты задачи, используя динамический путь из default.yaml
        self.limit_trace = self._load_task_limits()

    def _load_task_limits(self):
        limit_cfg = self.config.get('limits', {})
        if not limit_cfg:
            return None

        source_type = limit_cfg.get('limit_type', 'constant')

        # 🌟 БЕРЕМ ПУТЬ ИЗ НАСТРОЕК DEFAULT.YAML (без хардкода!)
        limit_dir_name = self.settings.get('limit_library_path', 'task_configs/limits')
        limit_lib_absolute = os.path.join(self.root_dir, limit_dir_name)

        # Передаем конфигурацию фабрике провайдеров
        provider = DataProviderFactory.get_provider(source_type, limit_lib_absolute, {
            'file_path': limit_cfg.get('limit_path'),
            'value': limit_cfg.get('limit_value'),
            'f_min': self.f_min_hz,
            'f_max': self.f_max_hz,
            'reader_settings': {
                'file_format': limit_cfg.get('file_format', 'text'),
                'skip_rows': limit_cfg.get('skip_rows', 1)  # Пропускаем шапку Excel
            },
            'columns_mapping': {'frequency': 0, 'value': 1, 'uncertainty': 2}
        })
        return provider.load_parameter().value_trace
