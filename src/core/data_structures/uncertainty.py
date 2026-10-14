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

    def __init__(self, frequencies: np.ndarray, values: np.ndarray,
                 frequencies_units: str = 'Hz', values_units: str = 'dB',
                 distribution_type: str = 'normal', k_factor: float | None = 2.0,
                 is_symmetric: bool = True, asymmetric_label: str = ""):
        super().__init__(frequencies, values, frequencies_units, values_units)
        self.distribution_type = distribution_type.lower()
        self.is_symmetric = is_symmetric
        self.asymmetric_label = asymmetric_label

        if self.distribution_type == 'normal':
            self.k_factor = float(k_factor if k_factor is not None else 2.0)
            self.divisor = self.k_factor
        elif self.distribution_type in self.DISTRIBUTION_DIVISORS:
            self.k_factor = None
            self.divisor = self.DISTRIBUTION_DIVISORS[self.distribution_type]
        else:
            raise ValueError(f'Неизвестное распределение: {self.distribution_type}')

    @classmethod
    def create_constant(cls, frequencies_units: str = 'Hz', values_units: str = 'dB',
                        distribution_type: str = 'rectangular', k_factor: float | None = None,
                        f_min: float = 9000.0, f_max: float = 40e9, value: float = 0.0,
                        is_symmetric: bool = True, asymmetric_label: str = ""):
        return cls(np.array([f_min, f_max]), np.array([value, value]),
                   frequencies_units, values_units, distribution_type, k_factor,
                   is_symmetric, asymmetric_label)

    def get_standard_uncertainty_for_frequencies(self, frequencies: np.ndarray) -> np.ndarray:
        return self.get_values_for_frequencies(frequencies) / self.divisor

    def get_max_uncertainties_in_range(self, f_min_hz: float, f_max_hz: float) -> tuple[float, float]:
        """
        🌟 АВТОНОМНЫЙ МЕТРОЛОГИЧЕСКИЙ РАСЧЕТ МАКСИМУМОВ:
        Возвращает кортеж (Максимальная_Сырая_Неопределенность, Максимальная_Стандартная_u)
        внутри заданного частотного окна на основе реальных физических точек.
        """
        slice_freqs, slice_raw_values = self.get_raw_slice(f_min_hz, f_max_hz)

        max_raw = float(np.max(slice_raw_values))
        max_std = float(np.max(slice_raw_values / self.divisor))

        return max_raw, max_std

    def align_to_grid(self, target_frequencies: np.ndarray) -> 'Uncertainty':
        """Возвращает новый объект Uncertainty, интерполированный под заданную сетку частот"""
        aligned_values = self.get_values_for_frequencies(target_frequencies)
        return Uncertainty(
            frequencies=target_frequencies,
            values=aligned_values,
            frequencies_units=self.frequencies_units,
            values_units=self.values_units,
            distribution_type=self.distribution_type,
            k_factor=self.k_factor
        )