# src/core/data_structures/parameter.py
import logging
from typing import Optional
import numpy as np
from .trace import Trace
from .uncertainty import Uncertainty

logger = logging.getLogger("Metrologix")


class Parameter:
    """Универсальный метрологический параметр прибора. Поддерживает красивую алгебру параметров"""

    def __init__(self, name: str, value_trace: Trace, uncertainty_trace: Optional[Uncertainty] = None) -> None:
        self.name = name
        self.value_trace = value_trace
        self.uncertainty_trace = uncertainty_trace
        self.raw_data = None


    def get_values_for_frequencies(self, target_frequencies: np.ndarray) -> tuple[np.ndarray, Optional[np.ndarray]]:
        """Унифицированная ленивая интерполяция. Возвращает None вместо u_std, если погрешности нет"""
        values = self.value_trace.get_values_for_frequencies(target_frequencies)
        if self.uncertainty_trace is not None:
            u_std = self.uncertainty_trace.get_standard_uncertainty_for_frequencies(target_frequencies)
            return values, u_std
        return values, None


    def get_raw_max_data_in_frequency_range(self, f_min: float, f_max: float, max_by: str = 'value',
                                            points_count: int = 2, freq_unit: str = 'Hz') -> tuple[Trace, Uncertainty|None]:
        if max_by == 'value':
            values_trace = self.value_trace.get_raw_max_values_in_frequency_range(f_min, f_max, points_count, freq_unit)
            uncertainty_trace = self.uncertainty_trace
            if uncertainty_trace is not None:
                frequencies = values_trace.frequencies
                uncertainty_values = uncertainty_trace.get_values_for_frequencies(frequencies)
                uncertainty_trace = Uncertainty(frequencies, uncertainty_values,
                                                freq_unit, uncertainty_trace.values_units,
                                                uncertainty_trace.distribution_type, uncertainty_trace.k_factor,
                                                uncertainty_trace.is_symmetric, uncertainty_trace.asymmetric_label)
            return values_trace, uncertainty_trace

            # return self.value_trace.get_raw_max_values_in_frequency_range(f_min, f_max, points_count, freq_unit)
        elif max_by == 'uncertainty':
            if self.uncertainty_trace is not None:
                uncertainty_trace = self.uncertainty_trace.get_raw_max_values_in_frequency_range(f_min, f_max,
                                                                                                 points_count,
                                                                                                 freq_unit)
                frequencies = uncertainty_trace.frequencies
                values = self.value_trace.get_values_for_frequencies(frequencies)
                values_trace = Trace(frequencies, values, freq_unit, self.value_trace.values_units)

                return values_trace, uncertainty_trace

                # return self.uncertainty_trace.get_raw_max_values_in_frequency_range(f_min, f_max, points_count, freq_unit)
            else:
                raise ValueError(f'В параметре {self.name} неопределенность не задана. '
                                 f'Вывод данных по максимуму неопределенности невозможен')
        else:
            raise ValueError(f'Тип данных {max_by} не поддерживается')


    def get_block_of_raw_data_for_frequencies(self, target_frequencies: np.ndarray):
        """
        Возвращает пачку исходных данных из raw_data для заданных частот
        :param target_frequencies: частоты на которых должны быть представлены данные
        :return: список Trace исходных данных для заданных частот
        """
        if len(self.raw_data) == 0:
            return []


        if not isinstance(self.raw_data, list):
            raise NotImplementedError(f'Не реализован вывод блока данных для {type(self.raw_data)}')

        block_of_raw_data = []
        for raw_piece_of_data in self.raw_data:
            block_of_raw_data.append(raw_piece_of_data.get_values_for_frequencies(target_frequencies))
        return block_of_raw_data


    def __add__(self, other: 'Parameter') -> 'Parameter':
        """Сложение параметров через оператор '+'"""
        new_value_trace = self.value_trace + other.value_trace

        new_uncertainty_trace = None
        if self.uncertainty_trace and other.uncertainty_trace:
            new_uncertainty_trace = self.uncertainty_trace + other.uncertainty_trace
        elif self.uncertainty_trace:
            new_uncertainty_trace = self.uncertainty_trace
        elif other.uncertainty_trace:
            new_uncertainty_trace = other.uncertainty_trace

        return Parameter(self.name, new_value_trace, new_uncertainty_trace)

    def __sub__(self, other: 'Parameter') -> 'Parameter':
        """Вычитание параметров через оператор '-' (Система 2 - Система 1)"""
        new_value_trace = self.value_trace - other.value_trace

        new_uncertainty_trace = None
        if self.uncertainty_trace and other.uncertainty_trace:
            # В метрологии погрешности при вычитании величин всё равно СКЛАДЫВАЮТСЯ по RSS!
            new_uncertainty_trace = self.uncertainty_trace + other.uncertainty_trace
        elif self.uncertainty_trace:
            new_uncertainty_trace = self.uncertainty_trace
        elif other.uncertainty_trace:
            new_uncertainty_trace = other.uncertainty_trace

        return Parameter(self.name, new_value_trace, new_uncertainty_trace)
