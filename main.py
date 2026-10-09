import os
from src.core.engine import MetrologixEngine

if __name__ == "__main__":
    # Корневой путь проекта
    root_directory = os.path.dirname(os.path.abspath(__file__))

    # Путь к конфигурационному файлу движка
    settings_config = os.path.join(root_directory, "settings", "default.yaml")
    # Путь к конфигурационному файлу запускаемой задачи
    task_config = os.path.join(root_directory, "task_configs", "conducted_task.yaml")

    # Инициализируем и запускаем Движок
    engine = MetrologixEngine(settings_config_path=settings_config,
                              task_config_path=task_config,
                              root_dir=root_directory)
    engine.run()
