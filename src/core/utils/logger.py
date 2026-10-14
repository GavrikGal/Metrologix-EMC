# src/core/utils/logger.py
import logging
import os
import sys


class MetrologixColorFormatter(logging.Formatter):
    """Кастомный форматировщик: раскрашивает дату, уровни и меняет цвет сообщения в зависимости от модуля"""

    # ANSI Цветовые коды
    RESET = "\033[0m"
    DATE_COLOR = "\033[90m"
    MODULE_NAME_COLOR = "\033[34m"

    # СЛОВАРЬ ЦВЕТОВ ДЛЯ УРОВНЕЙ ЛОГА [INFO]/[DEBUG]/[WARNING]/[ERROR]
    LEVEL_COLORS = {
        'DEBUG': "\033[2;31m",  # Тусклый темно-серый (чтобы отладка не мозолила глаза)
        'INFO': "\033[32m",  # Зеленый для штатной информации
        'WARNING': "\033[33m",  # Желтый для предупреждений
        'ERROR': "\033[1;31m",  # Красный для ошибок приборов/расчетов
        'CRITICAL': "\033[1;31m"  # Ярко-красный жирный для падений системы
    }

    # Цвета для сообщений в зависимости от "глубины" (имени модуля)
    MODULE_COLORS = {
        'main': "\033[1;37m",
        'engine': "\033[1;37m",  # Яркий белый (Верхний уровень - Главный диспетчер)
        'task': "\033[37m",  # Обычный белый
        'hardware': "\033[37m",  # Обычный белый
        'budget_calculator': "\033[34m",  # Синий (Средний уровень - Математика)
        'report_orchestrator': "\033[34m",  # Синий (Средний уровень - Координатор отчетов)
        'plot_renderer': "\033[90m",  # Темно-серый (Глубокий уровень - Рендереры)
        'table_renderer': "\033[90m",  # Темно-серый
        'correction_renderer': "\033[90m",  # Темно-серый
    }

    # Дефолтный цвет для модулей, которые не описаны в словаре (например, кастомные провайдеры)
    DEFAULT_MSG_COLOR = "\033[32m"  # Зеленый

    def __init__(self, fmt: str, datefmt: str, use_colors: bool = True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        # АВТОМАТИЧЕСКОЕ ИМЕНОВАНИЕ МОДУЛЯ
        # Превращаем техническое имя 'report_orchestrator' в красивое '[Report Orchestrator]'
        raw_module = record.module
        formatted_module_name = raw_module.replace('_', ' ').title()
        record.module_name = formatted_module_name

        # Если цвета выключены (например, для файла лога), отдаем стандартный текст
        if not self.use_colors:
            return super().format(record)

        # КАСТОМИЗАЦИЯ ЦВЕТОВ ОТ УРОВНЯ ВЛОЖЕННОСТИ СЕРВИСОВ
        # Определяем цвет текста сообщения на основе имени модуля
        msg_color = self.MODULE_COLORS.get(raw_module, self.DEFAULT_MSG_COLOR)

        # 2. КАСТОМИЗАЦИЯ ЦВЕТОВ УРОВНЯ ЛОГА
        # Ищем цвет в словаре LEVEL_COLORS. Если уровень кастомный, по умолчанию красим в белый (37)
        level_color = self.LEVEL_COLORS.get(record.levelname, "\033[37m")

        # Собираем строку из цветных блоков вручную с использованием ANSI-последовательностей
        asctime_str = f"{self.DATE_COLOR}{self.formatTime(record, self.datefmt)}{self.RESET}"
        module_str = f"{self.MODULE_NAME_COLOR}{formatted_module_name}{self.RESET}"
        level_str = f"{level_color}{record.levelname}{self.RESET}"
        message_str = f"{msg_color}{record.getMessage()}{self.RESET}"

        return f"{asctime_str} [{level_str}]: [{module_str}] {msg_color}{message_str}{self.RESET}"


def setup_logger(logging_config: dict, root_dir: str) -> logging.Logger:
    """Глобальная настройка системы логирования на основе default.yaml"""
    log_level_str = logging_config.get('level', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    logger = logging.getLogger("Metrologix")
    logger.setLevel(log_level)

    if logger.hasHandlers():
        logger.handlers.clear()

    log_format = logging_config.get('format', '%(asctime)s [%(module_name)s] [%(levelname)s] %(message)s')
    date_format = logging_config.get('date_format', '%Y-%m-%d %H:%M:%S')
    use_colors = logging_config.get('use_colors', True)

    # 1. Настройка вывода в консоль (Исправляем красный цвет!)
    if logging_config.get('log_to_console', True):
        # 🌟 ВАЖНО: Перенаправляем поток в sys.stdout (стандартный вывод) вместо stderr,
        # чтобы IDE перестала подсвечивать обычные информационные логи красным цветом!
        console_handler = logging.StreamHandler(sys.stdout)

        # Подключаем наш кастомный цветовой форматировщик
        console_formatter = MetrologixColorFormatter(log_format, date_format, use_colors=use_colors)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # 2. Настройка записи в файл лога (В файле цвета не нужны — они превратятся в мусорные ANSI-символы)
    if logging_config.get('log_to_file', True):
        log_file_name = logging_config.get('file_name', 'metrologix.log')
        log_file_path = os.path.join(root_dir, log_file_name)

        file_handler = logging.FileHandler(log_file_path, encoding='utf-8', mode='w')
        # Для текстового файла принудительно выключаемuse_colors
        file_formatter = MetrologixColorFormatter(log_format, date_format, use_colors=False)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger
