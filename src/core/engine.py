# src/core/engine.py
import os
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
        self.task = Task(task_config_path, self.settings, root_dir)

        hw_lib_absolute = os.path.join(root_dir, self.settings.get('hardware_library_path'))
        self.hardware = Hardware(hw_lib_absolute)

    def run(self) -> None:
        print(f"\n--- Запуск выполнения сессии: {self.task.name} ---")

        # 1. Сборка измерительной схемы и запуск чтения сырых файлов приборов
        setup_cfg = self.task.config.get('hardware_setup', {})
        self.hardware.build_tract(setup_cfg)
        self.hardware.process_all_devices()

        # 2. Расчет метрологического бюджета СИСПР (Чистая математика ядра)
        print("\n[Engine] Запуск метрологического калькулятора СИСПР 16-4-2...")
        budget_data = CISPRBudgetCalculator.calculate_emc_budget(self.task, self.hardware)

        # 3. Генерация Excel-книги суммарного бюджета
        frequency_range_string = FrequencyConverter.format_frequency_range(
            self.task.frequency_min_hz,  # 🌟 ИСПРАВЛЕНО НА ПОЛНОЕ ИМЯ
            self.task.frequency_max_hz  # 🌟 ИСПРАВЛЕНО НА ПОЛНОЕ ИМЯ
        )

        ExcelExporter.export_emc_budget(
            output_dir=self.task.output_dir,
            task_name=self.task.name,
            method_name=self.task.config.get('target_method', 'EMC Method'),
            freq_range_str=frequency_range_string,
            budget_data=budget_data
        )

        # 🌟 4. ЛОГИКА УПРАВЛЕНИЯ ВЫВОДОМ ОТЧЕТОВ СИЛАМИ ENGINE 🌟
        orchestrator = ReportOrchestrator(self.settings, self.task, self.hardware)

        proto_cfg = self.task.config.get('protocol_output', {})
        corr_cfg = self.task.config.get('hardware_corrections_output', {})

        # Проверяем флаги в конфигурации текущей задачи
        if proto_cfg and proto_cfg.get('generate_plots', False):
            print("[Engine] Команда: сформировать спектральные графики...")
            orchestrator.generate_plots()

        if proto_cfg and proto_cfg.get('generate_data_tables', False):
            print("[Engine] Команда: выгрузить таблицы реальных отсчетов...")
            orchestrator.generate_data_tables()

        if corr_cfg and corr_cfg.get('generate_corrections', False):
            print("[Engine] Команда: выгрузить калибровочные файлы для приборов...")
            orchestrator.generate_hardware_corrections()

        print(f"\n--- Задача {self.task.name} успешно завершена! Данные сохранены в output. ---")
