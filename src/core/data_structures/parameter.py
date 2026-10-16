# src/core/data_structures/parameter.py
from typing import Optional
import numpy as np
from .trace import Trace
from .uncertainty import Uncertainty


class Parameter:
    """Универсальный метрологический параметр прибора. Поддерживает красивую алгебру параметров"""

    def __init__(self, name: str, value_trace: Trace, uncertainty_trace: Optional[Uncertainty] = None) -> None:
        self.name = name
        self.value_trace = value_trace
        self.uncertainty_trace = uncertainty_trace

    def get_values_for_frequencies(self, target_frequencies: np.ndarray) -> tuple[np.ndarray, Optional[np.ndarray]]:
        """Унифицированная ленивая интерполяция. Возвращает None вместо u_std, если погрешности нет"""
        values = self.value_trace.get_values_for_frequencies(target_frequencies)
        if self.uncertainty_trace is not None:
            u_std = self.uncertainty_trace.get_standard_uncertainty_for_frequencies(target_frequencies)
            return values, u_std
        return values, None

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
