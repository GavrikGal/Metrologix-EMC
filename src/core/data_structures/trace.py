import numpy as np


class Trace:
    def __init__(self, frequencies: np.ndarray,
                 values: np.ndarray,
                 frequencies_units: str = 'Hz',
                 values_units: str = 'dB') -> None:
        self.frequencies = np.array(frequencies)
        self.values = np.array(values)
        self.frequencies_units = frequencies_units
        self.values_units = values_units

    @classmethod
    def create_constant(cls, f_min: float, f_max: float, value: float,
                        frequencies_units: str = 'Hz', values_units: str = 'dB'):
        """Фабричный метод: хранит 2 крайние точки диапазона"""
        return cls(
            frequencies=np.array([f_min, f_max]),
            values=np.array([value, value]),
            frequencies_units=frequencies_units,
            values_units=values_units
        )

    def get_value_at(self, frequency: float) -> float:
        """Получение интерполированного значения на заданной частоте"""
        return float(np.interp(frequency, self.frequencies, self.values))

    def get_values_for_frequencies(self, frequencies: np.ndarray) -> np.ndarray:
        """Получение интерполированных значений для массива заданных частот"""
        return np.interp(frequencies, self.frequencies, self.values)

    def get_raw_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Для протокола: возвращает сырые неизмененные точки калибровки/измерений"""
        return self.frequencies, self.values