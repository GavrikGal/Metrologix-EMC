# src/core/data_structures/uncertainty.py
import numpy as np
from .trace import Trace

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
                 k_factor: float | None = 2.0):
        super().__init__(frequencies, values, frequencies_units, values_units)
        self.distribution_type = distribution_type.lower()

        # Привязываем метрологические константы и делители СИСПР 16-4-2
        if self.distribution_type == 'normal':
            if k_factor is None:
                self.k_factor = 2.0
            else:
                self.k_factor = float(k_factor)
            self.divisor = self.k_factor

        elif self.distribution_type in self.DISTRIBUTION_DIVISORS:
            self.k_factor = None  # Для ненормальных распределений k не указывается
            self.divisor = self.DISTRIBUTION_DIVISORS[self.distribution_type]

        else:
            raise ValueError(f'Неизвестное распределение: {self.distribution_type}. '
                             f'Доступные: {list(self.DISTRIBUTION_DIVISORS.keys())}')

    @classmethod
    def create_constant(cls,
                        f_min: float,
                        f_max: float,
                        value: float,
                        frequencies_units: str = 'Hz',
                        values_units: str = 'dB',
                        distribution_type: str = 'normal',
                        k_factor: float | None = 2.0):
        """Фабричный метод для создания константной неопределенности"""
        frequencies = np.array([f_min, f_max])
        constant_values = np.full_like(frequencies, fill_value=value, dtype=float)
        return cls(frequencies, constant_values, frequencies_units, values_units, distribution_type, k_factor)

    def get_standard_uncertainty_at(self, frequency: float) -> float:
        expanded_uncertainty = self.get_value_at(frequency)
        return expanded_uncertainty / self.divisor

    def get_standard_uncertainty_for_frequencies(self, frequencies: np.ndarray) -> np.ndarray:
        return self.get_values_for_frequencies(frequencies) / self.divisor
