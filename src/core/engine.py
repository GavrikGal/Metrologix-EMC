import os
import yaml
import numpy as np
from src.hardware.rf_cable.rf_cable import RFCableSystem
from src.reports.visualizer import Visualizer


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

    def run(self):
        """Главный рабочий цикл Движка — теперь короткий, понятный и чистый"""
        print(f"\n--- Запуск задачи: {self.task_name} ---")

        # 1. Собираем измерительную систему
        self.build_measurement_system()

        # 2. Запускаем расчет физики внутренних данных приборов
        for role, device in self.active_devices.items():
            device.process_device_data()

        # 3. Генерируем графики (код вынесен в отдельный метод)
        self._generate_all_plots()

        # 4. ЗАГЛУШКА: Расчет общего бюджета неопределенности ЭМС
        print("\n[Engine] Расчет суммарного бюджета неопределенности ЭМС пропущен (заглушка).")
        print(f"--- Задача {self.task_name} успешно выполнена. Результаты в output/{self.task_name} ---")
