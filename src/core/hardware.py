# src/core/hardware.py
import os
from src.hardware.rf_cable.rf_cable import RFCableSystem
from src.hardware.receiver.receiver import EMCReceiver
from src.hardware.lisn.lisn import LISN
from src.hardware.process.measurement_process import MeasurementProcess


class Hardware:
    """Управляет составом оборудования измерительного тракта и его метрологическими данными"""

    def __init__(self, hardware_library_path: str) -> None:
        self.hardware_library_path = hardware_library_path
        self.devices = {}  # Хранилище: { "device_role": DeviceObject }

    def build_tract(self, hardware_setup_config: dict) -> None:
        """Регистрирует приборы в схеме по их уникальным ролям из конфигурации задачи"""
        for device_role, folder_name in hardware_setup_config.items():
            device_dir = os.path.join(self.hardware_library_path, folder_name)

            if 'receiver' in device_role:
                device = EMCReceiver(device_dir)
            elif 'cable' in device_role or 'attenuator' in device_role:
                device = RFCableSystem(device_dir)
            elif 'lisn' in device_role:
                device = LISN(device_dir)
            else:
                device = MeasurementProcess(device_dir)

            self.devices[device_role] = device

    def process_all_devices(self) -> None:
        """Запускает чтение и кэширование параметров для всего оборудования"""
        for device in self.devices.values():
            device.process_device_data()

    def get_device(self, device_role: str):
        return self.devices.get(device_role)
