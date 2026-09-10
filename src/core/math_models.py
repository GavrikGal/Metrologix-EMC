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


class DistributionDecomposition:
    """
    Математический модуль для приведения различных законов распределения погрешностей
    к Стандартной Неопределенности (u(xi), k=1) согласно ISO/IEC Guide 98-3 (GUM).
    """

    @staticmethod
    def to_standard(value: np.ndarray, dist_type: str, **kwargs) -> np.ndarray:
        """
        Делит исходное значение погрешности на коэффициент, соответствующий закону распределения.

        :param value: Массив NumPy или одиночное число (значение погрешности/неопределенности в дБ)
        :param dist_type: Строка, задающая закон ('rectangular', 'u-shaped', 'triangle', 'normal', 'trapezoidal')
        :param kwargs: Дополнительные параметры (например, k_factor для нормального или beta для трапеции)
        """
        # Приводим к нижнему регистру, чтобы избежать ошибок из-за разного регистра в YAML
        dist_type = dist_type.strip().lower()

        if dist_type == 'rectangular' or dist_type == 'flat':
            # Прямоугольное (равномерное) распределение — применяется для большинства приборов,
            # когда погрешность задана пределами ±а (например, по паспорту)
            return value / np.sqrt(3)

        elif dist_type == 'u-shaped' or dist_type == 'u':
            # U-образное распределение — применяется для погрешностей рассогласования (mismatch)
            # из-за неопределенности фазы коэффициентов отражения в ВЧ трактах
            return value / np.sqrt(2)

        elif dist_type == 'triangle' or dist_type == 'triangular':
            # Треугольное распределение — применяется, когда значения вблизи центра диапазона
            # более вероятны, чем у границ
            return value / np.sqrt(6)

        elif dist_type == 'normal' or dist_type == 'gaussian':
            # Нормальное (Гауссово) распределение — применяется для данных из свидетельств о калибровке.
            # По умолчанию в ЭМС калибровка идет с уровнем доверия 95%, что соответствует k = 2.
            k_factor = kwargs.get('k_factor', 2)
            return value / k_factor

        elif dist_type == 'trapezoidal':
            # Трапециевидное распределение — промежуточный вариант между прямоугольным и треугольным.
            # Требует параметр beta (отношение длины плоской вершины к основанию трапеции, от 0 до 1).
            beta = kwargs.get('beta', 0.5)
            if not (0 <= beta <= 1):
                raise ValueError("Параметр 'beta' для трапециевидного распределения должен быть в диапазоне [0, 1]")
            return value / np.sqrt(6 * (1 + beta ** 2))

        elif dist_type == 'standard' or dist_type == 'k1':
            # Если данные уже являются стандартной неопределенностью (например, рассчитанный Тип А)
            return value

        else:
            raise ValueError(
                f"Критическая ошибка: неизвестный закон распределения '{dist_type}' в конфигурации прибора.")
