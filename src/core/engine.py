import os

import pandas as pd
import yaml
import numpy as np
from src.hardware.rf_cable.rf_cable import RFCableSystem
from src.reports.visualizer import Visualizer
from src.reports.template_exporter import TemplateExporter
from src.core.math_models import FrequencyConverter


class MetrologixEngine:
    """Главный управляющий движок системы Metrologix EMC"""

    def __init__(self, task_config_path: str, root_dir: str):
        self.root_dir = root_dir
        self.task_config_path = task_config_path

        with open(task_config_path, 'r', encoding='utf-8') as f:
            self.task_config = yaml.safe_load(f)

        self.task_name = self.task_config.get('task_name', 'Default_Task')
        self.task_output_dir = os.path.join(root_dir, "output", self.task_name)
        os.makedirs(self.task_output_dir, exist_ok=True)

        self.active_devices = {}

    def build_measurement_system(self):
        """Сканирует hardware_setup задачи и создает объекты приборов из библиотеки"""
        setup = self.task_config.get('hardware_setup', {})
        hardware_lib_path = os.path.join(self.root_dir, "hardware_library")

        for role, folder_name in setup.items():
            device_dir = os.path.join(hardware_lib_path, folder_name)
            if not os.path.exists(device_dir):
                raise FileNotFoundError(f"Папка оборудования '{folder_name}' не найдена в {hardware_lib_path}")

            # Внутри цикла сборки схемы в engine.py:
            if role == 'cable_system':
                self.active_devices[role] = RFCableSystem(device_dir)
            elif role == 'receiver':
                from src.hardware.receiver.receiver import EMCReceiver
                self.active_devices[role] = EMCReceiver(device_dir)
            elif role == 'reading_process':
                # КЛАСС ПРОЦЕССА/ОПЕРАТОРА
                from src.hardware.process.measurement_process import MeasurementProcess
                self.active_devices[role] = MeasurementProcess(device_dir)

            print(f"[Engine] В схему на роль '{role}' назначен прибор: {self.active_devices[role].name}")

    def _generate_target_frequencies(self, device, param_name: str, settings: dict) -> np.ndarray:
        """
        Универсальный генератор целевой сетки частот на основе конфигурации задачи.
        Разделяет логику метода формирования (grid_type) и масштаба осей (scale_type).
        """
        grid_type = settings.get('frequency_grid_type', 'by_points_count').strip().lower()
        scale_type = settings.get('scale_type', 'linear').strip().lower()

        # 🎯 Метод 1: Строго точки калибровки из файлов прибора (k=1 прослеживаемость)
        if grid_type == 'calibration_points':
            return device.get_default_frequencies(param_name)

        # 🎯 Метод 2: Фиксированный пользовательский список частот из YAML с конвертацией единиц
        if grid_type == 'custom_list':
            custom_freqs = settings.get('custom_frequencies', [])
            if not custom_freqs:
                raise ValueError(
                    f"[Engine] Выбран режим 'custom_list', но массив 'custom_frequencies' пуст для {device.name}")

            # Находим, в каких единицах пользователь ввел список (по умолчанию Hz)
            user_unit = settings.get('custom_frequencies_unit', 'Hz').strip()

            # 💡 УМНЫЙ ПЕРЕВОД: Считаем коэффициент перевода из единиц пользователя в системные Гц
            # Например, если user_unit='MHz', то get_ratio('MHz', 'Hz') вернет 1e6
            conversion_ratio = FrequencyConverter.get_ratio(from_unit=user_unit, to_unit='Hz')

            # Переводим весь список частот в Герцы и превращаем в отсортированный NumPy массив
            freqs_in_hz = np.array(custom_freqs, dtype=float) * conversion_ratio
            return np.sort(freqs_in_hz)

        # Для расчетных методов (по шагу или количеству точек) извлекаем физический диапазон прибора
        hardware_freqs = device.get_default_frequencies(param_name)
        f_min = float(settings.get('freq_min_hz', hardware_freqs.min()))
        f_max = float(settings.get('freq_max_hz', hardware_freqs.max()))

        # 🎯 Метод 3: Сетка строится по заданному шагу по частоте
        if grid_type == 'by_step':
            if scale_type == 'log':
                # Логарифмический шаг на основе множителя (умножение на коэффициент)
                multiplier = float(settings.get('step_multiplier', 1.1))
                if multiplier <= 1.0:
                    raise ValueError(
                        "[Engine] Для логарифмического шага 'step_multiplier' должен быть строго больше 1.0")
                freqs = []
                current_f = f_min
                while current_f <= f_max:
                    freqs.append(current_f)
                    current_f *= multiplier
                return np.array(freqs)
            else:
                # Классический линейный шаг частоты, например, через каждые 10 кГц
                step = float(settings.get('step_value_hz', 10e3))
                return np.arange(f_min, f_max + step, step)

        # 🎯 Метод 4: Сетка строится по фиксированному количеству точек (by_points_count)
        pts_count = int(settings.get('points_count', 300))
        if scale_type == 'log':
            return np.logspace(np.log10(f_min), np.log10(f_max), num=pts_count)
        else:
            return np.linspace(f_min, f_max, num=pts_count)

    def _prepare_parameter_data(self, role_id: str, param_name: str, settings: dict) -> tuple[
        np.ndarray, np.ndarray, np.ndarray]:
        """Модернизированный метод подготовки векторов данных с умной сеткой частот"""
        device = self.active_devices.get(role_id)
        if not device:
            raise ValueError(f"Устройство для роли '{role_id}' не найдено в текущей схеме.")

        # 💡 ГЕНЕРИРУЕМ ЧАСТОТНУЮ СЕТКУ НА ОСНОВЕ ОПЦИЙ ЗАДАЧИ
        frequencies = self._generate_target_frequencies(device, param_name, settings)

        # Запрашиваем интерполированные (или точечные) векторы у прибора
        y_values, u_standard = device.get_parameter_vector(param_name, frequencies)

        return frequencies, y_values, u_standard

    def _generate_protocol_materials(self):
        """Универсальный метод генерации отчетных материалов протокола (графиков и таблиц) по кастомным единицам"""
        proto_cfg = self.task_config.get('protocol_output', {})
        if not proto_cfg or not self.active_devices:
            return

        print("\n[Engine] Начало формирования отчетных материалов протокола...")
        gen_plots = proto_cfg.get('generate_plots', False)
        gen_tables = proto_cfg.get('generate_data_tables', False)

        # Импортируем наши разделенные классы отчетов
        from src.reports.visualizer import Visualizer
        from src.reports.protocol_table_exporter import ProtocolTableExporter

        for item in proto_cfg.get('items', []):
            role_id = item.get('device_id')
            param_name = item.get('target_parameter')  # 💡 Извлекаем параметр динамически из задачи!
            show_unc = item.get('show_uncertainty', True)

            device = self.active_devices.get(role_id)
            if not device:
                continue

            for sub in item.get('sub_plots', []):
                # 💡 УМНЫЙ ПЕРЕВОД ЕДИНИЦ ДЛЯ КАЖДОГО ПОДГРАФИКА ИНДИВИДУАЛЬНО
                sub_unit = sub.get('unit', 'Hz')
                ratio_to_hz = FrequencyConverter.get_ratio(from_unit=sub_unit, to_unit='Hz')

                f_min_hz = float(sub.get('freq_min')) * ratio_to_hz
                f_max_hz = float(sub.get('freq_max')) * ratio_to_hz

                # Генерируем красивую строку диапазона частот для имени файла через наш Converter
                freq_range_str = FrequencyConverter.format_frequency_range(f_min_hz, f_max_hz)

                # 💡Передаем в метод f_min_hz и f_max_hz текущего поддиапазона среза
                filename_base = self._build_informative_filename(device, param_name, f_min_hz, f_max_hz)

                # Формируем итоговое красивое имя, добавляя суффикс (title)
                safe_title = sub.get('title').replace(" ", "_").replace("-", "")
                final_filename = f"{filename_base} - {safe_title}"

                try:
                    # 💥 АКТИВИРУЕМ ГРАФИКИ
                    if gen_plots:
                        freqs_plot, values_plot, u_std_plot = self._prepare_parameter_data(
                            role_id=role_id, param_name=param_name,
                            settings={'frequency_grid_type': 'by_points_count',
                                      'scale_type': sub.get('x_scale', 'linear'),
                                      'freq_min_hz': f_min_hz, 'freq_max_hz': f_max_hz, 'points_count': 400}
                        )
                        Visualizer.draw_subplot(
                            output_dir=self.task_output_dir, device_name=device.name, filename=final_filename,
                            freqs_hz=freqs_plot, values=values_plot, u_std=u_std_plot,
                            sub_cfg=sub, show_unc=show_unc
                        )

                    # АКТИВИРУЕМ ЖИВЫЕ ТАБЛИЦЫ ПРОТОКОЛА (Строго без интерполяции)
                    if gen_tables and 'table_points_count' in sub:
                        pts_count = int(sub.get('table_points_count', 30))

                        raw_slice = device.get_raw_measurement_slice(
                            param_name=param_name, f_min_hz=f_min_hz, f_max_hz=f_max_hz, points_count=pts_count
                        )

                        # 💡 ИСПРАВЛЕНИЕ: Передаем param_name последним аргументом!
                        ProtocolTableExporter.export_raw_slice(
                            output_dir=self.task_output_dir,
                            filename=final_filename,
                            raw_slice_data=raw_slice,
                            target_unit=sub_unit,
                            param_name=param_name  # Передаем динамическое имя параметра
                        )

                except Exception as e:
                    print(f"[Engine] Ошибка формирования материалов для диапазона '{sub.get('title')}': {e}")

    def _get_receiver_export_rules(self, receiver_folder: str) -> tuple[dict, str, dict]:
        """Вспомогательный метод: загружает и валидирует правила экспорта приемника"""
        if not receiver_folder:
            raise ValueError("В схеме задачи не задана роль 'receiver'.")

        rx_dir = os.path.join(self.root_dir, "hardware_library", receiver_folder)
        config_path = os.path.join(rx_dir, "device_config.yaml")

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Конфиг приемника не найден: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            rx_cfg = yaml.safe_load(f)

        rules = rx_cfg.get('correction_export_rules', {})
        if not rules:
            raise KeyError(f"Приемник '{receiver_folder}' не поддерживает экспорт коррекций (нет блока правил).")

        return rules, rx_dir, rx_cfg

    def _build_informative_filename(self, device, param_name: str, f_min_hz: float, f_max_hz: float) -> str:
        """
        Генерирует базовое имя файла по ГОСТ-шаблону:
        'Device_Type, Short_ID №SN (Текущий диапазон частот среза)' без расширения.
        """
        dev_cfg = device.config

        # Собираем текстовую информацию о приборе
        dev_type = dev_cfg.get('device_type', 'Device')
        short_id = dev_cfg.get('device_short_id', 'Unknown')
        sn_suffix = f" №{dev_cfg['serial_number']}" if 'serial_number' in dev_cfg else ""

        base_name = f"{dev_type}, {short_id}{sn_suffix}"

        # 💡 ИСПРАВЛЕНИЕ: Используем УМНЫЙ конвертер для КРАСИВОЙ строки ТЕКУЩЕГО диапазона частот,
        # который передан из конкретного поддиапазона задачи, а не всего диапазона железа!
        freq_range_str = FrequencyConverter.format_frequency_range(f_min_hz, f_max_hz)

        # Результат: "Cable, Cable №SN-99999 (150.00 kHz - 30.00 MHz)"
        filename = f"{base_name} ({freq_range_str})"

        # Очистка от запрещенных символов файловых систем
        for char in ['*', ':', '"', '<', '>', '|', '?']:
            filename = filename.replace(char, '')
        return filename

    def _process_hardware_corrections(self):
        """Управляет генерацией файлов коррекции. Настройки инверсии и параметров берутся из задачи."""
        corr_cfg = self.task_config.get('hardware_corrections_output', {})
        if not corr_cfg.get('generate_corrections', False):
            return

        print("\n[Engine] Начало генерации файлов коррекции через текстовые шаблоны...")
        receiver_folder = self.task_config['hardware_setup'].get('receiver')

        try:
            # Загружаем правила экспорта выбранного анализатора
            rules, rx_dir, rx_cfg = self._get_receiver_export_rules(receiver_folder)
            template_path = os.path.join(rx_dir, rules.get('template_file'))
            target_freq_unit = rules.get('target_freq_unit', 'MHz')

            from src.reports.template_exporter import TemplateExporter

            # Итерируемся по списку оборудования из задачи, для которого включен экспорт
            for device_role, settings in corr_cfg.get('devices_to_export', {}).items():
                if not settings.get('export', False):
                    continue

                device = self.active_devices.get(device_role)
                if not device:
                    continue

                param_name = settings.get('target_parameter')
                if not param_name:
                    print(
                        f"[Engine] Ошибка: для роли '{device_role}' не указан 'target_parameter' в настройках экспорта.")
                    continue

                if param_name not in device.processed_parameters:
                    raise KeyError(f"Прибор {device.name} не имеет рассчитанного параметра '{param_name}'")

                # Опрашиваем диапазон частот строго для обрабатываемого параметра
                hardware_freqs = device.processed_parameters[param_name]['freq']

                export_settings = settings.copy()
                if 'freq_min_hz' not in export_settings:
                    export_settings['freq_min_hz'] = hardware_freqs.min()
                if 'freq_max_hz' not in export_settings:
                    export_settings['freq_max_hz'] = hardware_freqs.max()

                # Подготавливаем сетку данных, используя наш универсальный метод
                freqs, values, _ = self._prepare_parameter_data(
                    role_id=device_role,
                    param_name=param_name,
                    settings=export_settings
                )

                multiplier = -1.0 if export_settings.get('invert_sign', False) else 1.0
                freq_ratio = FrequencyConverter.get_ratio(from_unit='Hz', to_unit=target_freq_unit)

                # Формируем подпапку hardware_corrections/Имя_Приемника и красивое имя файла
                corr_dir = os.path.join(self.task_output_dir, "hardware_corrections", receiver_folder)

                # Извлекаем физические границы всего диапазона железа из кэша
                hardware_freqs = device.processed_parameters[param_name]['freq']
                f_hardware_min = hardware_freqs.min()
                f_hardware_max = hardware_freqs.max()

                # Извлекаем расширение из имени файла шаблона (например, .csv)
                _, ext = os.path.splitext(rules.get('template_file', '.csv'))

                # 💡 ИСПРАВЛЕНИЕ: Передаем границы всего доступного диапазона железа
                filename_base = self._build_informative_filename(device, param_name, f_hardware_min, f_hardware_max)
                full_output_path = os.path.join(corr_dir, f"{filename_base}{ext}")

                # Запускаем универсальный рендеринг шаблона
                TemplateExporter.export_correction(
                    template_path=template_path,
                    output_path=full_output_path,
                    frequencies=freqs.tolist(),
                    values=values.tolist(),
                    freq_convert_ratio=freq_ratio,
                    sign_multiplier=multiplier,
                    meta_params=rules.get('template_meta', {})
                )

        except Exception as e:
            print(f"[Engine Ошибка]: Не удалось выгрузить коррекции для оборудования: {e}")

    def _calculate_total_emc_budget(self):
        """Расчет инструментального бюджета неопределенности. Логика вывода делегирована в ExcelExporter."""
        b_cfg = self.task_config.get('budget_range_settings', {})
        budget_comp = self.task_config.get('budget_composition', [])

        if not b_cfg or not budget_comp:
            print("[Engine Budget] Пропуск расчета: в задаче отсутствуют настройки диапазона или состава бюджета.")
            return

        print("\n[Engine] Сборка и расчет суммарного бюджета неопределенности ЭМС...")

        # Переводим границы частот задачи в системные Герцы
        task_unit = b_cfg.get('unit', 'Hz')
        ratio_to_hz = FrequencyConverter.get_ratio(from_unit=task_unit, to_unit='Hz')
        f_min_hz = b_cfg.get('freq_min') * ratio_to_hz
        f_max_hz = b_cfg.get('freq_max') * ratio_to_hz

        # Строим красивую строку диапазона частот для заголовка отчета
        freq_range_str = FrequencyConverter.format_frequency_range(f_min_hz, f_max_hz)

        raw_budget_data = []

        # Динамически опрашиваем устройства схемы по описанию из файла задачи
        for item in budget_comp:
            comp_name = item.get('component_name', 'Unknown Constituent')
            role_id = item.get('device_role')
            param_name = item.get('target_parameter')

            device = self.active_devices.get(role_id)
            if not device:
                print(f"[Engine Budget] Предупреждение: Роль '{role_id}' не задействована в схеме. Пропуск.")
                continue

            # Запрашиваем метрологический паспорт максимума для полосы частот задачи
            unc_passport = device.get_max_standard_uncertainty(param_name, f_min_hz, f_max_hz)

            # Красиво мапим закон распределения (убираем путаницу)
            dist_name = unc_passport['distribution'].upper()
            dist_str = f"NORMAL (k={unc_passport['k_factor']})" if dist_name == 'NORMAL' else dist_name

            # Накапливаем чистые сырые данные для передачи экспортеру отчетов
            raw_budget_data.append({
                'name': comp_name,
                'device': f"{device.name} (S/N: {device.config.get('serial_number', 'None')})",
                'raw_val': float(unc_passport['raw_value']),
                'dist': dist_str,
                'u_std': float(unc_passport['standard_uncertainty'])
            })

        # ДЕЛЕГИРУЕМ ВЫВОД РЕЗУЛЬТАТОВ СПЕЦИАЛИЗИРОВАННОМУ КЛАССУ EXCEL EXPORTER
        from src.reports.budget_exporter import ExcelExporter

        ExcelExporter.export_emc_budget(
            output_dir=self.task_output_dir,
            task_name=self.task_name,
            method_name=self.task_config.get('target_method', 'EMC Method'),
            freq_range_str=freq_range_str,
            budget_data=raw_budget_data
        )

    def run(self):
        """Главный рабочий цикл Движка — строго последовательный и изолированный"""
        print(f"\n--- Запуск задачи: {self.task_name} ---")

        # 1. Собираем измерительную схему
        self.build_measurement_system()

        # 2. Запускаем расчет физики внутренних данных приборов (СТРОГО ОДИН ЦИКЛ)
        print("\n[Engine] Расчет и загрузка метрологических параметров оборудования...")
        for role, device in self.active_devices.items():
            device.process_device_data()

        # 3. 💡 ИСПРАВЛЕНИЕ: Вызываем материалы протокола строго ПОСЛЕ завершения всех расчетов приборов!
        self._generate_protocol_materials()

        # 4. Выгружаем файлы коррекций для флешки анализатора
        self._process_hardware_corrections()

        # 5. Расчет суммарного инструментального бюджета неопределенности ЭМС по СИСПР
        self._calculate_total_emc_budget()