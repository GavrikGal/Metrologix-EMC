# src/core/engine.py
import os
from src.core.task_context import TaskContext
from src.core.measurement_chain import MeasurementChain
from src.core.budget_calculator import CISPRBudgetCalculator
from src.reports.report_orchestrator import ReportOrchestrator
from src.reports.budget_exporter import ExcelExporter
from src.core.math_models import FrequencyConverter


class MetrologixEngine:
    """Главный управляющий оркестратор всей системы"""

    def __init__(self, settings_config: dict, task_config_path: str, root_dir: str) -> None:
        self.settings = settings_config
        self.context = TaskContext(task_config_path, self.settings, root_dir)

        hw_lib_absolute = os.path.join(root_dir, self.settings.get('hardware_library_path'))
        self.chain = MeasurementChain(hw_lib_absolute)

    def run(self) -> None:
        print(f"\n--- Запуск выполнения сессии: {self.context.task_name} ---")

        # 1. Сборка измерительной схемы и запуск чтения сырых файлов приборов
        setup_cfg = self.context.config.get('hardware_setup', {})
        self.chain.build_chain(setup_cfg)
        self.chain.process_all_devices()

        # 2. Расчет метрологического бюджета СИСПР (Чистая математика ядра)
        print("\n[Engine] Запуск метрологического калькулятора СИСПР 16-4-2...")
        budget_data = CISPRBudgetCalculator.calculate_emc_budget(self.context, self.chain)

        # 3. Передача результатов расчета на генерацию Excel-книги бюджета
        freq_range_str = FrequencyConverter.format_frequency_range(self.context.f_min_hz, self.context.f_max_hz)
        ExcelExporter.export_emc_budget(
            output_dir=self.context.output_dir, task_name=self.context.task_name,
            method_name=self.context.config.get('target_method', 'EMC Method'),
            freq_range_str=freq_range_str, budget_data=budget_data
        )

        # 🌟 4. ЛОГИКА УПРАВЛЕНИЯ ВЫВОДОМ ОТЧЕТОВ СИЛАМИ ENGINE 🌟
        orchestrator = ReportOrchestrator(self.settings, self.context, self.chain)

        proto_cfg = self.context.config.get('protocol_output', {})
        corr_cfg = self.context.config.get('hardware_corrections_output', {})

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

        print(f"\n--- Задача {self.context.task_name} успешно завершена! Данные сохранены в output. ---")
