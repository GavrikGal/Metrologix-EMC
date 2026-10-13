# src/core/utils/trace_manipulator.py
import numpy as np
from src.core.data_structures.trace import Trace

class TraceManipulator:
    """Манипулятор трасс: выполняет внешние математические операции над метрологическими сущностями"""

    @staticmethod
    def concatenate_grids(trace_a: Trace, trace_b: Trace) -> tuple[Trace, Trace]:
        """
        Принимает две любые трассы (или неопределенности), склеивает их частотные сетки
        (30 кГц + 100 кГц), убирает дубликаты и возвращает два новых объекта,
        интерполированных под эту общую плотную сетку частот.
        """
        # Объединяем оси частот двух объектов, удаляем дубликаты и сортируем по возрастанию
        combined_frequencies = np.concatenate((trace_a.frequencies, trace_b.frequencies))
        union_grid = np.sort(np.unique(combined_frequencies))

        # Перестраиваем (интерполируем) оба объекта под общую сетку частот
        aligned_a = trace_a.align_to_grid(union_grid)
        aligned_b = trace_b.align_to_grid(union_grid)

        return aligned_a, aligned_b
