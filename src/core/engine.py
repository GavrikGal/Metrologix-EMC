# src/core/engine.py
import os
import logging
from src.core.task import Task
from src.core.hardware import Hardware
from src.core.tract import Tract  # 🌟 Наш новый каскадный модуль
from src.core.budget_calculator import CISPRBudgetCalculator
from src.reports.report_orchestrator import ReportOrchestrator
from src.reports.budget_exporter import ExcelExporter
from src.core.math_models import FrequencyConverter


class MetrologixEngine:
    def __init__(self, settings_config: dict, task_config_path: str, root_dir: str) -> None:
        self.settings = settings_config
        self.task = Task(task_config_path, self.settings, root_dir)
        self.logger = logging.getLogger("Metrologix")

        hardware_library_dir = self.settings.get('hardware_library_path', 'hardware_library')
        hardware_library_absolute = os.path.join(root_dir, hardware_library_dir)
        self.hardware = Hardware(hardware_library_absolute)

    def run(self) -> None:
        self.logger.info(f"Старт выполнения измерительной сессии: {self.task.name}")

        # 1. Загрузка чистых первичных данных приборов на их родных частотах
        hardware_setup_config = self.task.config.get('hardware_setup', {})
        self.hardware.build_tract(hardware_setup_config)
        self.hardware.process_all_devices(self.task)

        # 🌟 2. ВЫЧИСЛЕНИЕ ВИРТУАЛЬНОГО РАССОГЛАСОВАНИЯ ЦЕПИ ТРАКТА
        self.logger.info("Расчет системного рассогласования ВЧ-тракта...")
        meas_tract = Tract(self.task, self.hardware)
        system_mismatch = meas_tract.calculate_total_mismatch()

        # 🌟 ИСПРАВЛЕНИЕ: Жёстко привязываем виртуальный параметр рассогласования к прибору кабеля,
        # к которому обращается CISPRBudgetCalculator во время сборки строк Excel!
        cable_device = self.hardware.get_device('cable_system')
        if cable_device:
            # Название ключа в словаре должно строго совпадать с target_parameter из conducted_task.yaml!
            cable_device.processed_parameters['Tract_Mismatch'] = system_mismatch

        # 3. Расчет метрологического бюджета СИСПР 16-4-2
        self.logger.info("Запуск метрологического калькулятора СИСПР 16-4-2...")
        budget_data = CISPRBudgetCalculator.calculate_emc_budget(self.task, self.hardware)

        # 4. Выгрузка книги Excel
        frequency_range_string = FrequencyConverter.format_frequency_range(self.task.frequency_min_hz,
                                                                           self.task.frequency_max_hz)
        ExcelExporter.export_emc_budget(
            output_dir=self.task.output_dir, task_name=self.task.name,
            method_name=self.task.config.get('target_method', 'EMC Method'),
            freq_range_str=frequency_range_string, budget_data=budget_data
        )

        # 5. Генерация отчетов (они возьмут чистые, неискаженные S21 конкретных девайсов!)
        orchestrator = ReportOrchestrator(self.settings, self.task, self.hardware)
        protocol_config = self.task.config.get('protocol_output', {})


        if protocol_config and protocol_config.get('generate_data_tables', False):
            orchestrator.generate_data_tables()
        if protocol_config and protocol_config.get('generate_plots', False):
            orchestrator.generate_plots()
        if self.task.config.get('hardware_corrections_output', {}).get('generate_corrections', False):
            orchestrator.generate_hardware_corrections()

        self.logger.info(f"Задача {self.task.name} успешно выполнена.")
