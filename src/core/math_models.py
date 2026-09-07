import numpy as np


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
