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
        """🌟 ПАСС 1: Загрузка первичных независимых параметров (константы, таблицы, разности)"""
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

    def process_calculated_parameters(self, task: Task, hardware: Hardware) -> None:
        """🌟 ПАСС 2: Расчет вторичных параметров взаимодействия (Mismatch), когда все базовые трассы готовы"""
        params_cfg = self.config.get('parameters', {})

        for param_name, target_cfg in params_cfg.items():
            src_type = target_cfg.get('source_type')

            if src_type != 'calculated_mismatch':
                continue
            elif src_type == 'calculated_mismatch':
                lisn = hardware.get_device('lisn')
                receiver = hardware.get_device('receiver')
                cable_system = hardware.get_device('cable_system')
                attenuator = hardware.get_device('attenuator')  # 🌟 Проверяем наличие аттенюатора

                if lisn and receiver and cable_system:
                    # 🌟 ФИЗИКА СИСПР: если подключен аттенюатор, его выходной S22 становится
                    # эквивалентным источником отражения для кабеля, гася переотражения от LISN
                    if attenuator and 'S22' in attenuator.processed_parameters:
                        target_cfg['source_vswr_trace'] = attenuator.processed_parameters['S22'].value_trace
                    else:
                        target_cfg['source_vswr_trace'] = lisn.processed_parameters['LISN_VSWR'].value_trace

                    # Характеристики нагрузки и кабеля остаются неизменными
                    target_cfg['load_vswr_trace'] = receiver.processed_parameters['Receiver_VSWR'].value_trace
                    target_cfg['cable_s21_trace'] = cable_system.processed_parameters['S21'].value_trace

                    if 'S11' in cable_system.processed_parameters:
                        target_cfg['cable_s11_trace'] = cable_system.processed_parameters['S11'].value_trace
                    if 'S22' in cable_system.processed_parameters:
                        target_cfg['cable_s22_trace'] = cable_system.processed_parameters['S22'].value_trace

                provider = DataProviderFactory.get_provider(
                    source_type=src_type, root_dir=self.device_dir_path, config=target_cfg
                )
                self.processed_parameters[param_name] = provider.get_parameter()
