# src/core/data_structures/parameter.py
from typing import Optional
import numpy as np
from .trace import Trace
from .uncertainty import Uncertainty


class Parameter:
    """
    Единый контейнер метрологического параметра.
    Хранит исходные (сырые) калибровочные или измерительные данные (Traces).
    """

    def __init__(self, value_trace: Trace, uncertainty_trace: Optional[Uncertainty] = None) -> None:
        self.value_trace = value_trace
        self.uncertainty_trace = uncertainty_trace

    def get_aligned_vectors(self, target_frequencies: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Ленивое вычисление (Lazy Evaluation): интерполирует значения
        и стандартную неопределенность под запрашиваемую сетку частот.
        """
        values = self.value_trace.get_values_for_frequencies(target_frequencies)

        # Если у параметра нет неопределенности, возвращаем вектор нулей (k=1)
        u_std = np.zeros_like(target_frequencies)
        if self.uncertainty_trace is not None:
            u_std = self.uncertainty_trace.get_standard_uncertainty_for_frequencies(target_frequencies)

        return values, u_std
