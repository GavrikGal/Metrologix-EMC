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

    def get_value_at(self, frequency: float) -> float:
        """Получение интерполированного значения на заданной частоте"""
        return float(np.interp(frequency, self.frequencies, self.values))

    def get_values_for_frequencies(self, frequencies: np.ndarray) -> np.ndarray:
        """Получение интерполированных значений для массива заданных частот"""
        return np.interp(frequencies, self.frequencies, self.values)

    def get_raw_frequencies(self) -> np.ndarray:
        """Возвращает исходные значения частот, которые были добавлены при инициализации"""
        return self.frequencies

    # def get_frequencies_units(self) -> str:
    #     """Возвращает единицы измерения частоты, по умолчанию Hz"""
    #     return self.frequencies_units
    #
    # def get_values_units(self) -> str:
    #     """Возвращает единицы измерения значений, по умолчанию dB"""
    #     return self.values_units