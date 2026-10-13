import os
import yaml
from src.core.engine import MetrologixEngine

if __name__ == "__main__":
    # 1. Определяем корневой путь проекта
    root_directory = os.path.dirname(os.path.abspath(__file__))

    # 2. Формируем абсолютные пути к файлам конфигураций
    settings_path = os.path.join(root_directory, "settings", "default.yaml")
    task_config_path = os.path.join(root_directory, "task_configs", "conducted_task.yaml")

    # 3. Читаем глобальные настройки приложения (settings)
    if not os.path.exists(settings_path):
        raise FileNotFoundError(f"Глобальный файл настроек не найден: {settings_path}")

    with open(settings_path, 'r', encoding='utf-8') as f:
        settings_dict = yaml.safe_load(f)

    # 4. Инициализируем и запускаем Движок по обновленной сигнатуре
    engine = MetrologixEngine(
        settings_config=settings_dict,  # Передаем готовый словарь настроек
        task_config_path=task_config_path,  # Путь к задаче Engine распарсит сам через TaskContext
        root_dir=root_directory
    )

    engine.run()


# import os
# from src.core.engine import MetrologixEngine
#
# if __name__ == "__main__":
#     # Корневой путь проекта
#     root_directory = os.path.dirname(os.path.abspath(__file__))
#
#     # Путь к конфигурационному файлу движка
#     settings_config = os.path.join(root_directory, "settings", "default.yaml")
#     # Путь к конфигурационному файлу запускаемой задачи
#     task_config = os.path.join(root_directory, "task_configs", "conducted_task.yaml")
#
#     # Инициализируем и запускаем Движок
#     engine = MetrologixEngine(settings_config_path=settings_config,
#                               task_config_path=task_config,
#                               root_dir=root_directory)
#     engine.run()
