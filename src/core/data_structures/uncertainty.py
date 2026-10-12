import numpy as np
from src.core.data_structures.trace import Trace


class Uncertainty(Trace):
    DISTRIBUTION_DIVISORS = {
        'normal': 2.0,
        'rectangular': np.sqrt(3.0),
        'u_shaped': np.sqrt(2.0),
        'triangular': np.sqrt(6.0),
    }

    def __init__(self,
                 frequencies: np.ndarray,
                 values: np.ndarray,
                 frequencies_units: str = 'Hz',
                 values_units: str = 'dB',
                 distribution_type: str = 'normal',
                 coverage_factor: float|None = 2.0
                 ):
        super().__init__(frequencies, values, frequencies_units, values_units)
        self.distribution_type = distribution_type.lower()

        if self.distribution_type == 'normal':
            if coverage_factor is None:
                self.coverage_factor = 2.0
            self.divisor = self.coverage_factor

        elif self.distribution_type in self.DISTRIBUTION_DIVISORS:
            if coverage_factor is not None:
                self.coverage_factor = None
            self.divisor = self.DISTRIBUTION_DIVISORS[self.distribution_type]

        else:
            raise ValueError(f'Неизвестное распределение: {self.distribution_type}'
                             f'Доступные: {list(self.DISTRIBUTION_DIVISORS.keys())}')


    @classmethod
    def create_constant(cls,
                        frequencies: np.ndarray,
                        value: float,
                        frequencies_units: str = 'Hz',
                        values_units: str = 'dB',
                        distribution_type: str = 'normal',
                        coverage_factor: float|None = 2
                        ):
        """Фабричный метод для создания константной неопределенности"""
        constant_values = np.full_like(frequencies, fill_value=value, dtype=float)
        return cls(frequencies, constant_values, frequencies_units, values_units, distribution_type, coverage_factor)

    def get_standard_uncertainty_at(self, frequency: float) -> float:
        """Возвращает стандартную неопределенность u(xi) на конкретной частоте"""
        expanded_uncertainty = self.get_value_at(frequency)
        return expanded_uncertainty / self.divisor

    def get_standard_uncertainty_for_frequencies(self, frequencies: np.ndarray) -> np.ndarray:
        """Получение интерполированных значений стандартной неопределенности для массива заданных частот"""
        return self.get_values_for_frequencies(frequencies) / self.divisor
