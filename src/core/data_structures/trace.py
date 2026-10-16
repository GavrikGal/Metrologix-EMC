# src/core/data_structures/trace.py
import numpy as np


class Trace:
    # Список разрешенных логарифмических шкал
    # LOGARITHMIC_UNITS = {'db', 'dbuv', 'dbuv/m', 'dbua', 'dbuv/m/mhz'}


    def __init__(self, frequencies: np.ndarray, values: np.ndarray,
                 frequencies_units: str = 'Hz', values_units: str = 'dB') -> None:
        # Используем np.copy(), чтобы гарантировать независимость массивов в памяти
        self.frequencies = np.copy(np.array(frequencies, dtype=float))
        self.values = np.copy(np.array(values, dtype=float))
        self.frequencies_units = frequencies_units.strip()
        self.values_units = values_units.strip()

    @classmethod
    def create_constant(cls, f_min: float, f_max: float, value: float,
                        frequencies_units: str = 'Hz', values_units: str = 'dB'):
        return cls(np.array([f_min, f_max]), np.array([value, value]), frequencies_units, values_units)

    @classmethod
    def create_zeros_like(cls, reference_trace: 'Trace') -> 'Trace':
        return cls(np.copy(reference_trace.frequencies), np.zeros_like(reference_trace.frequencies),
                   reference_trace.frequencies_units, reference_trace.values_units)


    def get_value_at(self, frequency: float) -> float:
        return float(np.interp(frequency, self.frequencies, self.values))

    def get_values_for_frequencies(self, frequencies: np.ndarray) -> np.ndarray:
        return np.interp(frequencies, self.frequencies, self.values)

    def align_to_grid(self, target_frequencies: np.ndarray) -> 'Trace':
        """Возвращает новый, независимый объект Trace на целевой сетке частот"""
        aligned_values = self.get_values_for_frequencies(target_frequencies)
        return Trace(target_frequencies, aligned_values, 'Hz', self.values_units)

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

    # =========================================================================
    # МЕТРОЛОГИЧЕСКИЕ КОНВЕРТЕРЫ ШКАЛ (ИММУТАБЕЛЬНЫЕ)
    # =========================================================================

    def to_linear(self) -> 'Trace':
        """Переводит логарифмические величины (содержащие 'db') в линейный масштаб 'linear'"""
        unit_lower = self.values_units.lower()
        if 'db' in unit_lower:
            # Честная физическая формула амплитуд без искусственного изменения знаков!
            linear_values = 10 ** (self.values / 20.0)
            return Trace(self.frequencies, linear_values, self.frequencies_units, 'linear')
        return Trace(self.frequencies, self.values, self.frequencies_units, self.values_units)

    def to_db(self) -> 'Trace':
        """Переводит линейный масштаб 'linear' обратно в логарифмические децибелы 'dB'"""
        unit_lower = self.values_units.lower()
        if 'db' in unit_lower:
            return Trace(self.frequencies, self.values, self.frequencies_units, self.values_units)

        if unit_lower == 'linear':
            db_values = 20.0 * np.log10(np.clip(self.values, 1e-10, None))
            return Trace(self.frequencies, db_values, self.frequencies_units, 'dB')
        return Trace(self.frequencies, self.values, self.frequencies_units, self.values_units)

    def swr_to_gamma(self) -> 'Trace':
        """Переводит трассу КСВН ('SWR'/'VSWR') в модуль коэффициента отражения 'linear'"""
        unit_lower = self.values_units.lower()
        if 'swr' not in unit_lower:
            return Trace(self.frequencies, self.values, self.frequencies_units, self.values_units)

        vswr_clipped = np.clip(self.values, 1.0, None)
        gamma_values = (vswr_clipped - 1.0) / (vswr_clipped + 1.0)
        return Trace(self.frequencies, gamma_values, self.frequencies_units, 'linear')

    # =========================================================================
    # МАТЕМАТИЧЕСКИЕ ОПЕРАТОРЫ С ЗАЩИТОЙ ЕДИНОГО КОНТЕКСТА СЕТОК
    # =========================================================================

    def __add__(self, other: 'Trace') -> 'Trace':
        self_db = self.to_db()
        other_db = other.to_db()

        # 🌟 ИСПРАВЛЕНИЕ: Если объекты УЖЕ лежат на одной частотной сетке,
        # не вызываем concatenate_grids, а просто складываем массивы, сохраняя контекст!
        if len(self_db.frequencies) == len(other_db.frequencies) and np.allclose(self_db.frequencies,
                                                                                 other_db.frequencies):
            return Trace(self_db.frequencies, self_db.values + other_db.values, 'Hz', self_db.values_units)

        from src.core.utils.trace_manipulator import TraceManipulator
        aligned_self, aligned_other = TraceManipulator.concatenate_grids([self_db, other_db])
        return Trace(aligned_self.frequencies, aligned_self.values + aligned_other.values, 'Hz',
                     self_db.values_units)

    def __sub__(self, other: 'Trace') -> 'Trace':
        self_db = self.to_db()
        other_db = other.to_db()

        if len(self_db.frequencies) == len(other_db.frequencies) and np.allclose(self_db.frequencies,
                                                                                 other_db.frequencies):
            return Trace(self_db.frequencies, self_db.values - other_db.values, 'Hz', self_db.values_units)

        from src.core.utils.trace_manipulator import TraceManipulator
        aligned_self, aligned_other = TraceManipulator.concatenate_grids([self_db, other_db])
        return Trace(aligned_self.frequencies, aligned_self.values - aligned_other.values, 'Hz',
                     self_db.values_units)

    def __mul__(self, other: 'Trace') -> 'Trace':
        self_lin = self.to_linear()
        other_lin = other.to_linear()

        if len(self_lin.frequencies) == len(other_lin.frequencies) and np.allclose(self_lin.frequencies,
                                                                                   other_lin.frequencies):
            return Trace(self_lin.frequencies, self_lin.values * other_lin.values, 'Hz', 'linear')

        from src.core.utils.trace_manipulator import TraceManipulator
        aligned_self, aligned_other = TraceManipulator.concatenate_grids([self_lin, other_lin])
        return Trace(aligned_self.frequencies, aligned_self.values * aligned_other.values, 'Hz', 'linear')