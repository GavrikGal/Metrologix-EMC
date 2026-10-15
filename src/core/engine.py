# src/core/engine.py
import os
import logging
from src.core.task import Task
from src.core.hardware import Hardware
from src.core.budget_calculator import CISPRBudgetCalculator
from src.reports.report_orchestrator import ReportOrchestrator
from src.reports.budget_exporter import ExcelExporter
from src.core.math_models import FrequencyConverter


class MetrologixEngine:
    """Главный управляющий оркестратор всей системы"""

    def __init__(self, settings_config: dict, task_config_path: str, root_dir: str) -> None:
        self.settings = settings_config
        # 1. Инициализируем задачу (она сама внутри себя загрузит и лимиты, и кривую СИСПР)
        self.task = Task(task_config_path, self.settings, root_dir)
        self.logger = logging.getLogger("Metrologix")

        hardware_library_dir = self.settings.get('hardware_library_path', 'hardware_library')
        hardware_library_absolute = os.path.join(root_dir, hardware_library_dir)
        self.hardware = Hardware(hardware_library_absolute)

    def run(self) -> None:
        self.logger.info(f"Старт выполнения измерительной сессии: {self.task.name}")

        # 🌟 1. Сборка измерительного тракта железа
        hardware_setup_config = self.task.config.get('hardware_setup', {})
        self.hardware.build_tract(hardware_setup_config)

        # 🌟 2. Обработка девайсов (передаем только self.task, старый код чтения кривой отсюда УДАЛЕН)
        self.hardware.process_all_devices(self.task)

        # 3. Расчет метрологического бюджета СИСПР 16-4-2 (Чистая математика ядра)
        self.logger.info(f"Запуск метрологического калькулятора СИСПР 16-4-2...")
        budget_data = CISPRBudgetCalculator.calculate_emc_budget(self.task, self.hardware)

        # 4. Передача результатов расчета на генерацию Excel-книги бюджета
        frequency_range_string = FrequencyConverter.format_frequency_range(
            self.task.frequency_min_hz,
            self.task.frequency_max_hz
        )
        ExcelExporter.export_emc_budget(
            output_dir=self.task.output_dir,
            task_name=self.task.name,
            method_name=self.task.config.get('target_method', 'EMC Method'),
            freq_range_str=frequency_range_string,
            budget_data=budget_data
        )

        # 5. Анализ конфигурации задачи силами контроллера Engine для точечного вывода отчетов
        orchestrator = ReportOrchestrator(self.settings, self.task, self.hardware)

        protocol_config = self.task.config.get('protocol_output', {})
        corrections_config = self.task.config.get('hardware_corrections_output', {})

        if protocol_config and protocol_config.get('generate_plots', False):
            self.logger.info("Формирование спектральных графиков отчетов...")
            orchestrator.generate_plots()

        if protocol_config and protocol_config.get('generate_data_tables', False):
            self.logger.info("Выгрузка таблиц реальных физических отсчетов для протокола...")
            orchestrator.generate_data_tables()

        if corrections_config and corrections_config.get('generate_corrections', False):
            self.logger.info("Экспорт файлов амплитудных коррекций для памяти приборов...")
            orchestrator.generate_hardware_corrections()

        self.logger.info(f"Задача {self.task.name} успешно выполнена.")
