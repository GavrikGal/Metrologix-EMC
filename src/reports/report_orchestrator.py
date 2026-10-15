# src/reports/report_orchestrator.py
import os
import numpy as np
from src.core.task import Task
from src.core.hardware import Hardware
from src.core.math_models import FrequencyConverter

# Импортируем наши изолированные компоненты-рендереры
from src.reports.renderers.plot_renderer import PlotRenderer
from src.reports.renderers.table_renderer import TableRenderer
from src.reports.renderers.correction_renderer import CorrectionRenderer


class ReportOrchestrator:
    """Исполнительный оркестратор отчетов: предоставляет точечные методы вывода для Engine"""

    def __init__(self, settings: dict, task: Task, hardware: Hardware) -> None:
        self.settings = settings
        self.task = task
        self.hardware = hardware

        # Инкапсулируем рендереры
        self.plot_renderer = PlotRenderer(settings.get("visualizer_setup", {}))
        self.table_renderer = TableRenderer()
        self.correction_renderer = CorrectionRenderer()

    def generate_plots(self) -> None:
        """Отрисовка спектральных графиков Matplotlib для всех элементов из задачи"""
        proto_cfg = self.task.config.get('protocol_output', {})
        if not proto_cfg or not proto_cfg.get('items'):
            return

        for item in proto_cfg.get('items', []):
            device_role = item.get('device_id')
            param_name = item.get('target_parameter')
            device = self.hardware.get_device(device_role)

            if not device or param_name not in device.processed_parameters:
                continue

            parameter = device.processed_parameters[param_name]
            device_folder = self.task.config['hardware_setup'].get(device_role)

            for sub in item.get('sub_plots', []):
                ratio = FrequencyConverter.get_ratio(from_unit=sub.get('unit', 'Hz'), to_unit='Hz')
                f_min_hz = float(sub.get('freq_min')) * ratio
                f_max_hz = float(sub.get('freq_max')) * ratio

                plot_freqs = np.linspace(f_min_hz, f_max_hz, num=400)
                interp_v, interp_u = parameter.get_aligned_vectors(plot_freqs)

                target_dir = os.path.join(self.task.output_dir, "plots", device_folder)
                self.plot_renderer.render(target_dir, device.config, param_name, plot_freqs, interp_v, interp_u, sub)

    def generate_data_tables(self) -> None:
        """Формирование CSV таблиц реальных физических отсчетов для всех элементов из задачи"""
        proto_cfg = self.task.config.get('protocol_output', {})
        if not proto_cfg or not proto_cfg.get('items'):
            return

        for item in proto_cfg.get('items', []):
            device_role = item.get('device_id')
            param_name = item.get('target_parameter')
            device = self.hardware.get_device(device_role)

            if not device or param_name not in device.processed_parameters:
                continue

            parameter = device.processed_parameters[param_name]
            device_folder = self.task.config['hardware_setup'].get(device_role)

            for sub in item.get('sub_plots', []):
                ratio = FrequencyConverter.get_ratio(from_unit=sub.get('unit', 'Hz'), to_unit='Hz')
                f_min_hz = float(sub.get('freq_min')) * ratio
                f_max_hz = float(sub.get('freq_max')) * ratio

                target_dir = os.path.join(self.task.output_dir, "protocol_tables", device_folder)
                pts_count = int(sub.get('table_points_count', 30))
                self.table_renderer.render(target_dir, device.config, param_name, parameter,
                                           f_min_hz, f_max_hz, pts_count, sub.get('unit', 'Hz'))

    def generate_hardware_corrections(self) -> None:
        """Выгрузка файлов амплитудных коррекций (поправок) для памяти ЭМС приборов"""
        corr_cfg = self.task.config.get('hardware_corrections_output', {})
        if not corr_cfg or not corr_cfg.get('devices_to_export'):
            return

        for device_role, settings in corr_cfg.get('devices_to_export', {}).items():
            if not settings.get('export', False):
                continue

            device = self.hardware.get_device(device_role)
            param_name = settings.get('target_parameter')

            if not device or param_name not in device.processed_parameters:
                continue

            target_freqs_hz = self._generate_target_frequencies(device, settings)
            device_folder = self.task.config['hardware_setup'].get(device_role)

            target_dir = os.path.join(self.task.output_dir, "hardware_corrections", device_folder)
            self.correction_renderer.render(target_dir, device, param_name, settings, target_freqs_hz)

    def _generate_target_frequencies(self, device, settings: dict) -> np.ndarray:
        """Служебный метод-хелпер для сборки координатных сеток частот"""
        grid_type = settings.get('frequency_grid_type', 'calibration_points').strip().lower()
        if grid_type == 'calibration_points':
            if not device.processed_parameters:
                return np.array([self.task.f_min_hz, self.task.f_max_hz])
            first_param = list(device.processed_parameters.values())[0]
            raw_f, _ = first_param.value_trace.get_raw_data()
            return raw_f

        if grid_type == 'custom_list':
            custom_freqs = settings.get('custom_frequencies', [])
            conversion_ratio = FrequencyConverter.get_ratio(from_unit=settings.get('custom_frequencies_unit', 'Hz'),
                                                            to_unit='Hz')
            return np.sort(np.array(custom_freqs, dtype=float) * conversion_ratio)

        f_min = float(settings.get('freq_min_hz', self.task.f_min_hz))
        f_max = float(settings.get('freq_max_hz', self.task.f_max_hz))
        if grid_type == 'by_step':
            return np.arange(f_min, f_max + float(settings.get('step_value_hz', 10e3)),
                             float(settings.get('step_value_hz', 10e3)))

        pts_count = int(settings.get('points_count', 300))
        return np.linspace(f_min, f_max, num=pts_count)
