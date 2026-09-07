# Файл: main.py
import os
from src.core.engine import MetrologixEngine

if __name__ == "__main__":
    # Определяем корневой путь проекта
    root_directory = os.path.dirname(os.path.abspath(__file__))

    # Путь к конфигурационному файлу запускаемой задачи
    task_config = os.path.join(root_directory, "task_configs", "conducted_task.yaml")

    # Инициализируем и запускаем Движок
    engine = MetrologixEngine(task_config_path=task_config, root_dir=root_directory)
    engine.run()
