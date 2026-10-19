# src/core/task.py
import os
import yaml
import logging

from src.core.data_structures.parameter import Parameter
from src.core.math_models import FrequencyConverter
from src.core.data_structures.trace import Trace
from src.readers.hardware_data_reader import HardwareDataReader
logger = logging.getLogger("Metrologix")


class Task:
    """Модель измерительной задачи. Хранит частотный диапазон, схему, лимиты и кривую СИСПР"""

    def __init__(self, task_config_path: str, settings: dict, root_dir: str):
        self.root_dir = root_dir
        self.settings = settings

        with open(task_config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.name = self.config.get('task_name', 'Default_Task')
        self.output_dir = os.path.join(root_dir, "output", self.name)

        # 1. Загрузка физических границ полосы частот задачи
        budget_settings = self.config.get('budget_range_settings', {})
        self.frequency_unit = budget_settings.get('unit', 'Hz')

        ratio_to_hz = FrequencyConverter.get_ratio(from_unit=self.frequency_unit, to_unit='Hz')
        self.frequency_min_hz = budget_settings.get('freq_min', 150e3) * ratio_to_hz
        self.frequency_max_hz = budget_settings.get('freq_max', 30e6) * ratio_to_hz

        # 2. Загружаем лимиты задачи
        self.limit_trace = self._load_limits()

        # 3. Загрузка кривой сигнал/шум
        self.noise_deviation_trace = self._load_noise_deviation_curve()

    def _load_limits(self) -> Parameter:
        limit_settings = self.config.get('limits', {})
        if not limit_settings:
            return None

        source_type = limit_settings.get('limit_type', 'constant')
        limit_dir_name = self.settings.get('limit_library_path', 'task_configs/limits')
        limit_library_absolute = os.path.join(self.root_dir, limit_dir_name)

        from src.readers.data_providers.provider_factory import DataProviderFactory
        provider = DataProviderFactory.get_provider(source_type, limit_library_absolute, {
            'file_path': limit_settings.get('limit_path'),
            'value': limit_settings.get('limit_value'),
            'f_min': self.frequency_min_hz,
            'f_max': self.frequency_max_hz,
            'reader_settings': limit_settings.get('reader_settings', {}),
            'columns_mapping': {'frequency': 0, 'value': 1, 'uncertainty': 2}
        })
        limits = provider.get_parameter()
        limits.name = 'Limits'
        return limits

    def _load_noise_deviation_curve(self) -> Parameter:
        """🌟 Служебный метод: читает график СИСПР через HardwareDataReader и возвращает Trace"""
        detector_type = self.config.get('target_detector', 'quasipeak').strip().lower()
        deviation_dir = self.settings.get('noise_deviation_path', 'task_configs/signal and noise deviation')

        file_name = f"{detector_type}.csv"
        # full_path = os.path.join(self.root_dir, deviation_dir, file_name)

        from src.readers.data_providers.provider_factory import DataProviderFactory
        provider = DataProviderFactory.get_provider('table', deviation_dir, {
            'file_path': file_name,
            'reader_settings': {
                'file_format': 'text',
                'skip_rows': 1,
                'delimiter': ',',
                'file_frequency_unit': 'Hz'
            }
        })

        noise_deviation_curve = provider.get_parameter()
        noise_deviation_curve.name = 'Noise_Deviation_Curve'
        return noise_deviation_curve
