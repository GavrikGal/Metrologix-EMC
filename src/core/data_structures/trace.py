# src/core/data_structures/trace.py
import numpy as np


class Trace:
    def __init__(self, frequencies: np.ndarray,
                 values: np.ndarray,
                 frequencies_units: str = 'Hz',
                 values_units: str = 'dB') -> None:
        self.frequencies = np.array(frequencies, dtype=float)
        self.values = np.array(values, dtype=float)
        self.frequencies_units = frequencies_units
        self.values_units = values_units

    @classmethod
    def create_constant(cls, f_min: float, f_max: float, value: float,
                        frequencies_units: str = 'Hz', values_units: str = 'dB'):
        """Фабричный метод для плоских константных трасс"""
        return cls(
            frequencies=np.array([f_min, f_max]),
            values=np.array([value, value]),
            frequencies_units=frequencies_units,
            values_units=values_units
        )

    def get_value_at(self, frequency: float) -> float:
        return float(np.interp(frequency, self.frequencies, self.values))

    def get_values_for_frequencies(self, frequencies: np.ndarray) -> np.ndarray:
        return np.interp(frequencies, self.frequencies, self.values)

    def get_raw_data(self) -> tuple[np.ndarray, np.ndarray]:
        return self.frequencies, self.values

    def get_raw_slice(self, f_min_hz: float, f_max_hz: float) -> tuple[np.ndarray, np.ndarray]:
        """
        МЕТРОЛОГИЧЕСКИЙ СРЕЗ: Возвращает реальные физические точки, попавшие в диапазон.
        Если это константа и точек внутри диапазона нет, возвращает границы диапазона задачи с этим значением.
        """
        mask = (self.frequencies >= f_min_hz) & (self.frequencies <= f_max_hz)

        if np.any(mask):
            return self.frequencies[mask], self.values[mask]

        # Защитная логика для констант ( evaluation):
        # Если калибровочные точки лежат за пределами (или их всего 2 на краях диапазона железа)
        target_freqs = np.array([f_min_hz, f_max_hz])
        return target_freqs, self.get_values_for_frequencies(target_freqs)

    def get_max_value_in_range(self, f_min_hz: float, f_max_hz: float) -> float:
        """Находит истинный максимум физической величины в заданном диапазоне частот"""
        _, slice_values = self.get_raw_slice(f_min_hz, f_max_hz)
        return float(np.max(slice_values))

    def align_to_grid(self, target_frequencies: np.ndarray) -> 'Trace':
        """
        МЕТРОЛОГИЧЕСКОЕ ВЫРАВНИВАНИЕ: Возвращает новый объект Trace,
        значения которого интерполированы под заданную сетку частот.
        """
        aligned_values = self.get_values_for_frequencies(target_frequencies)
        return Trace(
            frequencies=target_frequencies,
            values=aligned_values,
            frequencies_units=self.frequencies_units,
            values_units=self.values_units
        )