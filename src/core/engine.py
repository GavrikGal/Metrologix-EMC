import os
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

            if role == 'cable_system':
                self.active_devices[role] = RFCableSystem(device_dir)
                print(f"[Engine] В схему на роль '{role}' назначен прибор: {self.active_devices[role].name}")

    def _prepare_parameter_data(self, role_id: str, param_name: str,
                                f_min: float, f_max: float,
                                scale_type: str = 'linear', points_count: int = 400) -> tuple[
        np.ndarray, np.ndarray, np.ndarray]:
        """
        УНИВЕРСАЛЬНЫЙ МЕТОД ПОДГОТОВКИ ДАННЫХ.
        Генерирует нужную частотную сетку и запрашивает векторы у прибора.
        Используется и для графиков, и (в будущем) для файлов коррекции.
        """
        device = self.active_devices.get(role_id)
        if not device:
            raise ValueError(f"Устройство для роли '{role_id}' не найдено в текущей схеме.")

        # Генерируем частотную сетку в зависимости от масштаба
        if scale_type == 'log':
            frequencies = np.logspace(np.log10(f_min), np.log10(f_max), num=points_count)
        else:
            frequencies = np.linspace(f_min, f_max, num=points_count)

        # Запрашиваем интерполированные данные через универсальный интерфейс BaseDevice
        y_values, u_standard = device.get_parameter_vector(param_name, frequencies)

        return frequencies, y_values, u_standard

    def _generate_all_plots(self):
        """Выделенный метод обработки и вывода графиков"""
        plots_cfg = self.task_config.get('plots_output', {})
        if not plots_cfg.get('generate_plots', False) or not self.active_devices:
            return

        print("\n[Engine] Начало генерации графиков...")
        for item in plots_cfg.get('items', []):
            role_id = item.get('device_id')
            param_name = item.get('parameter')
            show_unc = item.get('show_uncertainty', True)

            device = self.active_devices.get(role_id)
            if not device:
                print(f"[Engine] Предупреждение: не могу нарисовать график, роль '{role_id}' не задействована.")
                continue

            for sub in item.get('sub_plots', []):
                try:
                    # Подготавливаем данные с помощью нашего нового универсального метода
                    freqs, values, u_std = self._prepare_parameter_data(
                        role_id=role_id,
                        param_name=param_name,
                        f_min=sub.get('freq_min_hz'),
                        f_max=sub.get('freq_max_hz'),
                        scale_type=sub.get('x_scale', 'linear'),
                        points_count=400
                    )

                    # Передаем чистые векторы Визуализатору
                    Visualizer.draw_subplot(
                        task_output_dir=self.task_output_dir,
                        device_name=device.name,
                        freqs=freqs,
                        values=values,
                        u_std=u_std,
                        sub_cfg=sub,
                        show_unc=show_unc
                    )
                except Exception as e:
                    print(f"[Engine] Ошибка визуализации подграфика '{sub.get('title')}': {e}")

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

    def _build_informative_filename(self, device, rules_cfg: dict) -> str:
        """Генерирует имя файла по ГОСТ-шаблону: 'Device_Type, Short_ID №SN (Частотный диапазон).ext'"""
        dev_cfg = device.config

        # 💡 КОРРЕКТНОЕ ИМЯ: 'device_type, device_short_id'
        dev_type = dev_cfg.get('device_type', 'Device')
        short_id = dev_cfg.get('device_short_id', 'Unknown')
        sn_suffix = f" №{dev_cfg['serial_number']}" if 'serial_number' in dev_cfg else ""

        base_name = f"{dev_type}, {short_id}{sn_suffix}"

        # Извлекаем физические границы частот оборудования из рассчитанного кэша
        param_name = "S21"
        freqs_hz = device.processed_parameters[param_name]['freq']

        f_min_mhz = freqs_hz.min() / 1e6
        f_max_ghz = freqs_hz.max() / 1e9

        # Автоматически подтягиваем расширение из имени файла шаблона
        _, ext = os.path.splitext(rules_cfg.get('template_file', '.csv'))

        # Итог: "Cable, Cable №SN-99999 (0.10 MHz - 40.00 GHz).csv"
        filename = f"{base_name} ({f_min_mhz:.2f} MHz - {f_max_ghz:.2f} GHz){ext}"

        # Очистка от запрещенных символов файловой системы
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
            # 1. Загружаем правила экспорта выбранного анализатора
            rules, rx_dir, rx_cfg = self._get_receiver_export_rules(receiver_folder)
            template_path = os.path.join(rx_dir, rules.get('template_file'))
            target_freq_unit = rules.get('target_freq_unit', 'MHz')

            # Импортируем наш универсальный класс экспорта
            from src.reports.template_exporter import TemplateExporter

            # 2. Итерируемся по списку оборудования из задачи, для которого включен экспорт
            for device_role, settings in corr_cfg.get('devices_to_export', {}).items():
                if not settings.get('export', False):
                    continue

                device = self.active_devices.get(device_role)
                if not device:
                    continue

                # 💡 ДИНАМИЧЕСКИЙ ПАРАМЕТР: берем имя параметра прямо из настроек текущей задачи
                param_name = settings.get('target_parameter', 'S21')
                if param_name not in device.processed_parameters:
                    raise KeyError(f"Прибор {device.name} не имеет рассчитанного параметра '{param_name}'")

                # Извлекаем физические границы
                hardware_freqs = device.processed_parameters[param_name]['freq']

                # Подготавливаем сглаженную сетку частот по настройкам шага из задачи
                freqs, values, _ = self._prepare_parameter_data(
                    role_id=device_role, param_name=param_name,
                    f_min=hardware_freqs.min(), f_max=hardware_freqs.max(),
                    scale_type='log' if settings.get('step_mode') == 'logspace' else 'linear',
                    points_count=settings.get('points_count', 300)
                )

                # 💡 ОПРЕДЕЛЯЕМ МНОЖИТЕЛЬ ЗНАКА: читаем флаг invert_sign из конфига задачи
                # Если invert_sign = true, то умножаем на -1.0, иначе на 1.0 (оставляем знак без изменений)
                multiplier = -1.0 if settings.get('invert_sign', False) else 1.0

                # Рассчитываем коэффициент перевода частот
                freq_ratio = FrequencyConverter.get_ratio(from_unit='Hz', to_unit=target_freq_unit)

                # Формируем подпапку hardware_corrections/Имя_Приемника и красивое имя файла
                corr_dir = os.path.join(self.task_output_dir, "hardware_corrections", receiver_folder)
                filename = self._build_informative_filename(device, rules)
                full_output_path = os.path.join(corr_dir, filename)

                # 3. Вызываем универсальный рендеринг Jinja2 шаблона
                TemplateExporter.export_correction(
                    template_path=template_path,
                    output_path=full_output_path,
                    frequencies=freqs.tolist(),
                    values=values.tolist(),
                    freq_convert_ratio=freq_ratio,
                    sign_multiplier=multiplier,  # Передаем рассчитанный множитель
                    meta_params=rules.get('template_meta', {})
                )

        except Exception as e:
            print(f"[Engine Ошибка]: Не удалось выгрузить коррекции для оборудования: {e}")

    def run(self):
        """Главный рабочий цикл Движка"""
        print(f"\n--- Запуск задачи: {self.task_name} ---")
        self.build_measurement_system()

        for role, device in self.active_devices.items():
            device.process_device_data()

        self._generate_all_plots()
        self._process_hardware_corrections()

        print("\n[Engine] Расчет суммарного бюджета неопределенности ЭМС пропущен (заглушка).")
        print(f"--- Задача {self.task_name} успешно выполнена. Результаты в output/{self.task_name} ---")