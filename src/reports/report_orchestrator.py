# src/reports/report_orchestrator.py
import os
import numpy as np
from src.core.task_context import TaskContext
from src.core.measurement_chain import MeasurementChain
from src.core.math_models import FrequencyConverter
from src.reports.visualizer import Visualizer
from src.reports.protocol_table_exporter import ProtocolTableExporter
from src.reports.template_exporter import TemplateExporter


class ReportOrchestrator:
    """Управляет формированием и выгрузкой всех отчетных и калибровочных материалов по ГОСТ стандарту"""

    def __init__(self, settings: dict, context: TaskContext, chain: MeasurementChain) -> None:
        self.settings = settings
        self.context = context
        self.chain = chain

    def generate_all_reports(self) -> None:
        """Запускает последовательную генерацию всех отчетных материалов"""
        self._generate_protocol_materials()
        self._generate_hardware_corrections()

    @staticmethod
    def _build_standard_filename(device_config: dict, f_min_hz: float, f_max_hz: float) -> str:
        """
        Генерирует строгое метрологическое имя файла по вашему стандарту:
        'Тип_девайса, Модель №SN (красивый_диапазон_частот)'
        """
        dev_type = device_config.get('device_type', 'Device')
        short_id = device_config.get('device_short_id', 'Unknown')
        sn = device_config.get('serial_number')
        sn_suffix = f" №{sn}" if sn and str(sn).lower() != 'none' else ""

        base_name = f"{dev_type}, {short_id}{sn_suffix}"
        freq_range_str = FrequencyConverter.format_frequency_range(f_min_hz, f_max_hz)

        filename = f"{base_name} ({freq_range_str})"

        # Очистка имени от запрещенных системных символов
        for char in ['*', ':', '"', '<', '>', '|', '?']:
            filename = filename.replace(char, '')
        return filename

    def _generate_target_frequencies(self, device, settings: dict) -> np.ndarray:
        """Универсальный генератор сетки частот для экспорта коррекций на основе YAML задачи"""
        grid_type = settings.get('frequency_grid_type', 'calibration_points').strip().lower()

        # Режим 1: Строго оригинальные точки поверки/измерений прибора
        if grid_type == 'calibration_points':
            # Извлекаем первую попавшуюся оригинальную ось частот из параметров девайса
            if not device.processed_parameters:
                return np.array([self.context.f_min_hz, self.context.f_max_hz])
            first_param = list(device.processed_parameters.values())[0]
            raw_f, _ = first_param.value_trace.get_raw_data()
            return raw_f

        # Режим 2: Фиксированный пользовательский список частот (custom_list) с переводом единиц
        if grid_type == 'custom_list':
            custom_freqs = settings.get('custom_frequencies', [])
            if not custom_freqs:
                raise ValueError(f"[Orchestrator] Выбран режим 'custom_list', но массив частот пуст для {device.name}")

            user_unit = settings.get('custom_frequencies_unit', 'Hz').strip()
            conversion_ratio = FrequencyConverter.get_ratio(from_unit=user_unit, to_unit='Hz')
            return np.sort(np.array(custom_freqs, dtype=float) * conversion_ratio)

        # Режимы по расчету (шаг или количество точек)
        f_min = float(settings.get('freq_min_hz', self.context.f_min_hz))
        f_max = float(settings.get('freq_max_hz', self.context.f_max_hz))
        scale_type = settings.get('scale_type', 'linear').strip().lower()

        # Режим 3: По фиксированному шагу частоты
        if grid_type == 'by_step':
            if scale_type == 'log':
                multiplier = float(settings.get('step_multiplier', 1.1))
                freqs = []
                current_f = f_min
                while current_f <= f_max:
                    freqs.append(current_f)
                    current_f *= multiplier
                return np.array(freqs)
            else:
                step = float(settings.get('step_value_hz', 10e3))
                return np.arange(f_min, f_max + step, step)

        # Режим 4: По фиксированному количеству точек (by_points_count)
        pts_count = int(settings.get('points_count', 300))
        if scale_type == 'log':
            return np.logspace(np.log10(f_min), np.log10(f_max), num=pts_count)
        else:
            return np.linspace(f_min, f_max, num=pts_count)

    def _generate_protocol_materials(self) -> None:
        proto_cfg = self.context.config.get('protocol_output', {})
        if not proto_cfg:
            return

        gen_plots = proto_cfg.get('generate_plots', False)
        gen_tables = proto_cfg.get('generate_data_tables', False)

        for item in proto_cfg.get('items', []):
            device_role = item.get('device_id')  # Роль в схеме (например, 'cable_system')
            param_name = item.get('target_parameter')
            device = self.chain.get_device(device_role)
            if not device:
                continue

            parameter = device.processed_parameters[param_name]
            # 🌟 Папку для девайса называем по имени его физического каталога из настроек железа
            device_folder_name = self.context.config['hardware_setup'].get(device_role)

            for sub in item.get('sub_plots', []):
                sub_unit = sub.get('unit', 'Hz')
                ratio = FrequencyConverter.get_ratio(from_unit=sub_unit, to_unit='Hz')
                f_min_hz = float(sub.get('freq_min')) * ratio
                f_max_hz = float(sub.get('freq_max')) * ratio

                # Формируем ЕДИНОЕ красивое имя файла по ГОСТу для текущего диапазона среза
                standard_filename = self._build_standard_filename(device.config, f_min_hz, f_max_hz)

                # --- ОТРИСОВКА ГРАФИКОВ ---
                if gen_plots:
                    plot_freqs_hz = np.linspace(f_min_hz, f_max_hz, num=400)
                    interp_values, interp_u_std = parameter.get_aligned_vectors(plot_freqs_hz)

                    # 🌟 Создаем графики и складываем в plots/Имя_Папки_Прибора
                    device_plots_dir = os.path.join(self.context.output_dir, "plots", device_folder_name)
                    visualizer = Visualizer(self.settings.get("visualizer_setup", {}))
                    visualizer.draw_subplot(device_plots_dir, device.config, param_name,
                                            plot_freqs_hz, interp_values, interp_u_std, sub, show_unc=True)

                # --- ВЫГРУЗКА ТАБЛИЦ ПРОТОКОЛА (СТРОГО РЕАЛЬНЫЕ ТОЧКИ) ---
                if gen_tables:
                    raw_freqs, raw_values = parameter.value_trace.get_raw_data()
                    mask = (raw_freqs >= f_min_hz) & (raw_freqs <= f_max_hz)
                    valid_indices = np.where(mask)[0]

                    if len(valid_indices) == 0:
                        continue

                    target_pts_count = int(sub.get('table_points_count', 30))
                    if len(valid_indices) <= target_pts_count:
                        chosen_indices = valid_indices
                    else:
                        ideal_grid = np.linspace(f_min_hz, f_max_hz, num=target_pts_count)
                        chosen_indices = []
                        for ideal_f in ideal_grid:
                            closest_idx = valid_indices[np.argmin(np.abs(raw_freqs[valid_indices] - ideal_f))]
                            if closest_idx not in chosen_indices:
                                chosen_indices.append(closest_idx)
                        chosen_indices = np.array(chosen_indices)

                    final_freqs = raw_freqs[chosen_indices]
                    final_values = raw_values[chosen_indices]

                    final_raw_unc = parameter.uncertainty_trace.get_values_for_frequencies(
                        final_freqs) if parameter.uncertainty_trace else np.zeros_like(final_freqs)

                    sys1 = parameter.__dict__.get('sys1_traces')
                    sys2 = parameter.__dict__.get('sys2_traces')
                    if sys1 is not None and sys2 is not None:
                        sys1_slice = sys1[chosen_indices, :]
                        sys2_slice = sys2[chosen_indices, :]
                        sys1_mean = np.mean(sys1_slice, axis=1)
                        sys2_mean = np.mean(sys2_slice, axis=1)
                    else:
                        sys1_slice = np.zeros((len(final_freqs), 1))
                        sys2_slice = np.zeros((len(final_freqs), 1))
                        sys1_mean = final_values
                        sys2_mean = final_values

                    raw_slice = {
                        'freq_hz': final_freqs, 'values_db': final_values, 'raw_uncertainty_db': final_raw_unc,
                        'sys1_traces': sys1_slice, 'sys2_traces': sys2_slice,
                        'sys1_mean_db': sys1_mean, 'sys2_mean_db': sys2_mean
                    }

                    # 🌟 Создаем таблицы и складываем в protocol_tables/Имя_Папки_Прибора
                    device_tables_dir = os.path.join(self.context.output_dir, "protocol_tables", device_folder_name)
                    ProtocolTableExporter.export_raw_slice(device_tables_dir, standard_filename, raw_slice, sub_unit,
                                                           param_name)

    def _generate_hardware_corrections(self) -> None:
        """Генерирует файлы коррекции строго по запрашиваемой в YAML сетке частот"""
        corr_cfg = self.context.config.get('hardware_corrections_output', {})
        if not corr_cfg or not corr_cfg.get('generate_corrections', False):
            return

        print("\n[ReportOrchestrator] Выгрузка файлов амплитудных коррекций оборудования...")
        devices_to_export = corr_cfg.get('devices_to_export', {})

        for device_role, settings in devices_to_export.items():
            if not settings.get('export', False):
                continue

            device = self.chain.get_device(device_role)
            param_name = settings.get('target_parameter')
            if not device or param_name not in device.processed_parameters:
                print(f"[ReportOrchestrator] Ошибка: параметр '{param_name}' для '{device_role}' не найден.")
                continue

            parameter = device.processed_parameters[param_name]
            device_folder_name = self.context.config['hardware_setup'].get(device_role)

            # Строим сетку частот на основе опций задачи (custom_list, calibration_points и т.д.)
            target_freqs_hz = self._generate_target_frequencies(device, settings)

            # Пересчитываем векторы методом ленивой интерполяции на целевую сетку
            interp_values, _ = parameter.get_aligned_vectors(target_freqs_hz)

            rules = device.config.get('correction_export_rules', {})
            if not rules:
                print(f"[ReportOrchestrator] Предупреждение: Устройство '{device_role}' не имеет правил экспорта.")
                continue

            template_file = rules.get('template_file')
            if not template_file:
                continue

            template_path = os.path.join(device.device_dir_path, template_file)
            target_freq_unit = rules.get('target_freq_unit', 'MHz')

            # Расчет метрологических коэффициентов трансформации знака и частот
            multiplier = -1.0 if settings.get('invert_sign', False) else 1.0
            freq_ratio = FrequencyConverter.get_ratio(from_unit='Hz', to_unit=target_freq_unit)

            # Имя файла коррекции формируется по общему ГОСТ шаблону
            standard_filename = self._build_standard_filename(device.config, target_freqs_hz.min(),
                                                              target_freqs_hz.max())
            _, ext = os.path.splitext(template_file)

            # Собираем путь выгрузки и вызываем Jinja2 рендерер
            corr_dir = os.path.join(self.context.output_dir, "hardware_corrections", device_folder_name)
            full_output_path = os.path.join(corr_dir, f"{standard_filename}{ext}")

            try:
                TemplateExporter.export_correction(
                    template_path=template_path, output_path=full_output_path,
                    frequencies=target_freqs_hz.tolist(), values=interp_values.tolist(),
                    freq_convert_ratio=freq_ratio, sign_multiplier=multiplier,
                    meta_params=rules.get('template_meta', {})
                )
            except Exception as e:
                print(f"[ReportOrchestrator] Ошибка рендеринга шаблона для {device_role}: {e}")

