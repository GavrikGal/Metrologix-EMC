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

    @staticmethod
    def join_sequences(traces: list[Trace]) -> Trace:
        """
        МЕТРОЛОГИЧЕСКОЕ СКЛЕИВАНИЕ ПОСЛЕДОВАТЕЛЬНОСТЕЙ:
        Склеивает последовательные файлы диапазонов шумов по вертикали.
        Сохраняет обе точки на стыках диапазонов для точного
        воспроизведения изменения RBW приемника
        """
        if not traces:
            raise ValueError("[TraceManipulator] Список трасс для склеивания пуст.")
        if len(traces) == 1:
            return traces[0]

        # Последовательно склеиваем массивы всех переданных кусков (декад/диапазонов)
        all_freqs = np.concatenate([t.frequencies for t in traces])
        all_values = np.concatenate([t.values for t in traces])

        # Выполняем СТАБИЛЬНУЮ сортировку (mergesort).
        # Она гарантирует, что если частоты равны (точка стыка),
        # то порядок следования точек из файлов сохранится без искажений!
        sort_indices = np.argsort(all_freqs, kind='mergesort')

        final_freqs = all_freqs[sort_indices]
        final_values = all_values[sort_indices]

        # Возвращаем единый непрерывный объект Trace, сохранивший все физические ступеньки
        return Trace(
            frequencies=final_freqs,
            values=final_values,
            frequencies_units=traces[0].frequencies_units,
            values_units=traces[0].values_units
        )