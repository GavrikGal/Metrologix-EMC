import numpy as np


class FrequencyConverter:
    """Универсальный метрологический конвертер единиц частоты"""
    _UNITS = {
        'hz': 1.0,
        'khz': 1e3,
        'mhz': 1e6,
        'ghz': 1e9
    }

    @classmethod
    def get_ratio(cls, from_unit: str, to_unit: str) -> float:
        """Возвращает множитель для перевода из одной единицы в другую"""
        f = from_unit.strip().lower()
        t = to_unit.strip().lower()
        if f not in cls._UNITS or t not in cls._UNITS:
            raise ValueError(f"Неподдерживаемая единица частоты. Допустимы: {list(cls._UNITS.keys())}")
        return cls._UNITS[f] / cls._UNITS[t]

    @classmethod
    def _get_best_unit(cls, freq_hz: float) -> str:
        """Вспомогательный метод: определяет оптимальную единицу для одного значения частоты"""
        if freq_hz >= 1e9:
            return "GHz"
        elif freq_hz >= 1e6:
            return "MHz"
        elif freq_hz >= 1e3:
            return "kHz"
        return "Hz"

    @staticmethod
    def format_frequency_range(f_min_hz: float, f_max_hz: float) -> str:
        """
        Полностью независимое форматирование нижней и верхней границ диапазона частот.
        Исключает зануление НЧ границ при широких ВЧ диапазонах тракта.
        """
        # 💡 УМНОЕ РЕШЕНИЕ: определяем единицы измерения независимо для каждого края
        unit_min = FrequencyConverter._get_best_unit(f_min_hz)
        unit_max = FrequencyConverter._get_best_unit(f_max_hz)

        # Получаем индивидуальные коэффициенты перевода из системных Гц
        ratio_min = FrequencyConverter.get_ratio(from_unit="Hz", to_unit=unit_min)
        ratio_max = FrequencyConverter.get_ratio(from_unit="Hz", to_unit=unit_max)

        f_min_scaled = f_min_hz * ratio_min
        f_max_scaled = f_max_hz * ratio_max

        # Форматируем красивую и наглядную метрологическую строку
        # Если единицы совпадают (например, 0.15 MHz - 30.00 MHz) -> выводим лаконично
        if unit_min == unit_max:
            return f"{f_min_scaled:.2f} - {f_max_scaled:.2f} {unit_max}"

        # Если единицы разные (например, 150.00 kHz - 40.00 GHz) -> каждая со своим размером!
        return f"{f_min_scaled:.2f} {unit_min} - {f_max_scaled:.2f} {unit_max}"


