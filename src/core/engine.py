import os
import yaml
import numpy as np
from src.hardware.rf_cable_systems.rf_cable_system import RFCableSystem
from src.reports.visualizer import Visualizer


class MetrologixEngine:
    """Главный управляющий движок системы EMC-SYS / Metrologix"""

    def __init__(self, task_config_path: str, root_dir: str):
        self.root_dir = root_dir
        self.task_config_path = task_config_path

        with open(task_config_path, 'r', encoding='utf-8') as f:
            self.task_config = yaml.safe_load(f)

        self.task_name = self.task_config.get('task_name', 'Default_Task')

        # Создаем корневую папку output для этой задачи
        self.task_output_dir = os.path.join(root_dir, "output", self.task_name)
        os.makedirs(self.task_output_dir, exist_ok=True)

        # Словарь активного оборудования схемы { 'cable_system': <объект_класса> }
        self.active_devices = {}

    def build_measurement_system(self):
        """Сканирует hardware_setup задачи и создает объекты приборов из корневой библиотеки"""
        setup = self.task_config.get('hardware_setup', {})
        hardware_lib_path = os.path.join(self.root_dir, "hardware_library")

        for role, folder_name in setup.items():
            device_dir = os.path.join(hardware_lib_path, folder_name)

            if not os.path.exists(device_dir):
                raise FileNotFoundError(f"Папка оборудования '{folder_name}' не найдена в {hardware_lib_path}")

            # Пока у нас готов только класс для кабелей/аттенюаторов.
            # В будущем здесь будет фабрика, выбирающая класс по девайс-тайпу.
            if role == 'cable_system':
                device_obj = RFCableSystem(device_dir)
                self.active_devices[role] = device_obj
                print(f"[Engine] В схему успешно добавлен компонент '{role}': {device_obj.name}")

    def run(self):
        print(f"\n--- Запуск задачи: {self.task_name} ---")

        # 1. Собираем схему из корневой библиотеки hardware_library
        self.build_measurement_system()

        # 2. Даем команду приборам распарсить файлы и посчитать свою физику
        for role, device in self.active_devices.items():
            device.process_device_data()

        # 3. Вывод графиков по настройкам задачи
        plots_cfg = self.task_config.get('plots_output', {})
        if plots_cfg.get('generate_plots') and self.active_devices:
            for item in plots_cfg.get('items', []):
                role_id = item.get('device_id')
                param_name = item.get('parameter')  # Наше "S21"

                device = self.active_devices.get(role_id)
                if not device:
                    print(f"[Engine] Предупреждение: устройство {role_id} не найдено в схеме.")
                    continue

                # Пробегаемся по подграфикам (диапазонам), которые настроил пользователь
                for sub in item.get('sub_plots', []):
                    f_min = sub.get('freq_min_hz')
                    f_max = sub.get('freq_max_hz')

                    # Создаем оптимальную сетку частот под конкретный диапазон графика
                    if sub.get('x_scale', 'linear') == 'log':
                        plot_frequencies = np.logspace(np.log10(f_min), np.log10(f_max), num=400)
                    else:
                        plot_frequencies = np.linspace(f_min, f_max, num=400)

                    try:
                        # Запрашиваем интерполированные векторы у девайса через универсальный интерфейс
                        y_values, u_standard = device.get_parameter_vector(param_name, plot_frequencies)

                        # ДВИЖОК ДЕЛЕГИРУЕТ ОТРИСОВКУ КЛАССУ VISUALIZER
                        Visualizer.draw_subplot(
                            task_output_dir=self.task_output_dir,
                            device_name=device.name,
                            freqs=plot_frequencies,
                            values=y_values,
                            u_std=u_standard,
                            sub_cfg=sub,
                            show_unc=item.get('show_uncertainty', True)
                        )

                    except Exception as e:
                        print(f"[Engine] Ошибка при передаче данных на визуализацию для {device.name}: {e}")

        # 4. ЗАГЛУШКА: Расчет общего бюджета неопределенности ЭМС
        print("\n[Engine] Расчет суммарного бюджета неопределенности ЭМС пропущен (заглушка).")
        print(f"--- Задача {self.task_name} успешно выполнена. Результаты в output/{self.task_name} ---")
