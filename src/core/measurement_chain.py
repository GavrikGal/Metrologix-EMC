# src/core/measurement_chain.py
import os
from src.hardware.rf_cable.rf_cable import RFCableSystem
from src.hardware.receiver.receiver import EMCReceiver
from src.hardware.lisn.lisn import LISN
from src.hardware.process.measurement_process import MeasurementProcess


class MeasurementChain:
    """Управляет физическим трактом. Позволяет добавлять дубликаты (кабель_1, кабель_2)"""

    def __init__(self, hardware_library_path: str) -> None:
        self.hardware_library_path = hardware_library_path
        self.devices = {}

    def build_chain(self, hardware_setup_cfg: dict) -> None:
        """
        Принимает структуру:
        hardware_setup:
          receiver: "keysight_n9030b"
          attenuator_3db: "pasternack_3db"
          attenuator_10db: "pasternack_10db"
          cable_system: "sucoflex_11m"
        """
        for unique_id, folder_name in hardware_setup_cfg.items():
            device_dir = os.path.join(self.hardware_library_path, folder_name)

            # Интеллектуальный маппинг классов
            if 'receiver' in unique_id:
                device = EMCReceiver(device_dir)
            elif 'cable' in unique_id or 'attenuator' in unique_id:
                device = RFCableSystem(device_dir)
            elif 'lisn' in unique_id:
                device = LISN(device_dir)
            else:
                device = MeasurementProcess(device_dir)

            self.devices[unique_id] = device

    def process_all_devices(self) -> None:
        for device in self.devices.values():
            device.process_device_data()

    def get_device(self, unique_id: str):
        return self.devices.get(unique_id)
