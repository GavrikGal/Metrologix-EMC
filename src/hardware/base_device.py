# src/hardware/base_device.py
from __future__ import annotations
import os
import yaml
from abc import ABC
from typing import TYPE_CHECKING
from src.readers.data_providers.provider_factory import DataProviderFactory

if TYPE_CHECKING:
    from src.core.hardware import Hardware
    from src.core.task import Task


class BaseDevice(ABC):
    def __init__(self, device_dir_path: str) -> None:
        self.device_dir_path = device_dir_path
        self.config_path = os.path.join(device_dir_path, "device_config.yaml")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.name = self.config.get('device_name', 'Unknown Device')
        self.processed_parameters = {}

    def process_device_data(self, task: Task) -> None:
        """Загрузка первичных независимых параметров (константы, таблицы, разности)"""
        params_cfg = self.config.get('parameters', {})

        for param_name, target_cfg in params_cfg.items():
            src_type = target_cfg.get('source_type')
            target_cfg['parameter_system_name'] = param_name

            # Пропускаем параметры, требующие перекрестных связей с другими устройствами
            if src_type == 'calculated_mismatch':
                continue

            if src_type == 'calculated_noise_floor':
                target_cfg['task_limit_trace'] = task.limit_trace
                target_cfg['cispr_graph_trace'] = task.noise_deviation_trace

            provider = DataProviderFactory.get_provider(
                source_type=src_type, root_dir=self.device_dir_path, config=target_cfg
            )
            self.processed_parameters[param_name] = provider.get_parameter()
