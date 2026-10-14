import os
import yaml
from src.core.engine import MetrologixEngine
from src.core.utils.logger import setup_logger

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

    logging_config = settings_dict.get('logging_setup', {})
    logger = setup_logger(logging_config, root_directory)

    logger.info("Система Metrologix EMC успешно инициализирована.")  # Тестовая запись

    # 4. Инициализируем и запускаем Движок по обновленной сигнатуре
    engine = MetrologixEngine(
        settings_config=settings_dict,  # Передаем готовый словарь настроек
        task_config_path=task_config_path,  # Путь к задаче Engine распарсит сам через TaskContext
        root_dir=root_directory
    )

    engine.run()
