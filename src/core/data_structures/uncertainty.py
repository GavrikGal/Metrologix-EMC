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
                   frequencies_units, values_units, distribution_type, k_factor, is_symmetric, asymmetric_label)


    @classmethod
    def create_zeros_like(cls, reference_trace: Trace, distribution_type: str = 'normal') -> 'Uncertainty':
        """Создает нулевую неопределенность на сетке опорной трассы"""
        return cls(
            frequencies=np.copy(reference_trace.frequencies),
            values=np.zeros_like(reference_trace.frequencies),
            frequencies_units=reference_trace.frequencies_units,
            values_units=reference_trace.values_units,
            distribution_type=distribution_type,
            k_factor=1.0 if distribution_type == 'normal' else None
        )


    def align_to_grid(self, target_frequencies: np.ndarray) -> 'Uncertainty':
        return Uncertainty(target_frequencies, self.get_values_for_frequencies(target_frequencies),
                           self.frequencies_units, self.values_units, self.distribution_type, self.k_factor,
                           self.is_symmetric, self.asymmetric_label)


    def get_standard_uncertainty_for_frequencies(self, frequencies: np.ndarray) -> np.ndarray:
        return self.get_values_for_frequencies(frequencies) / self.divisor


    def get_max_uncertainties_in_range(self, f_min_hz: float, f_max_hz: float) -> tuple[float, float]:
        slice_freqs, slice_raw_values = self.get_raw_slice(f_min_hz, f_max_hz)
        return float(np.max(slice_raw_values)), float(np.max(slice_raw_values / self.divisor))

    def get_raw_max_values_in_frequency_range(self, f_min: float, f_max: float,
                                              points_count: int = 2, freq_unit: str = 'Hz') -> 'Trace':
        uncertainty_trace = super().get_raw_max_values_in_frequency_range(f_min, f_max, points_count, freq_unit)
        uncertainty_trace.values = uncertainty_trace.values / self.divisor
        return Uncertainty(uncertainty_trace.frequencies, uncertainty_trace.values,
                           freq_unit, self.values_units, self.distribution_type, self.k_factor,
                           self.is_symmetric, self.asymmetric_label)


    # =========================================================================
    # МЕТРОЛОГИЧЕСКИЙ RSS ПОЛИМОРФИЗМ
    # =========================================================================

    def __add__(self, other: 'Uncertainty') -> 'Uncertainty':
        """Геометрическое RSS сложение стандартных неопределенностей строго в дБ шкал"""
        self_db = self.to_db()
        other_db = other.to_db()

        from src.core.utils.trace_manipulator import TraceManipulator
        aligned_self, aligned_other = TraceManipulator.concatenate_grids([self_db, other_db])

        # Делим на делитель формы, получая стандартную u(xi)
        u_std_self = aligned_self.values / self.divisor
        u_std_other = aligned_other.values / other.divisor

        rss_values = np.sqrt(u_std_self ** 2 + u_std_other ** 2)

        return Uncertainty(aligned_self.frequencies, rss_values, aligned_self.frequencies_units,
                           'dB', 'normal', k_factor=1.0)