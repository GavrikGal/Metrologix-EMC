import os
import yaml
from abc import ABC, abstractmethod
from src.readers.data_providers.provider_factory import DataProviderFactory



class BaseDevice(ABC):
    def __init__(self, device_dir_path: str) -> None:
        self.device_dir_path = device_dir_path
        self.config_path = os.path.join(device_dir_path, "device_config.yaml")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.name = self.config.get('device_name', 'Unknown Device')
        self.processed_parameters = {}  # Хранилище: { "param_name": Parameter }

    def process_device_data(self) -> None:
        """Автоматическая сборка параметров из конфигурации прибора"""
        params_cfg = self.config.get('parameters', {})

        for param_name, target_cfg in params_cfg.items():
            src_type = target_cfg.get('source_type')

            provider = DataProviderFactory.get_provider(
                source_type=src_type,
                root_dir=self.device_dir_path,
                config=target_cfg
            )
            self.processed_parameters[param_name] = provider.get_parameter()
