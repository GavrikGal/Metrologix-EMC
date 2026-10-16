# src/core/utils/trace_manipulator.py
import numpy as np
from src.core.data_structures.trace import Trace

class TraceManipulator:
    """Манипулятор трасс: выполняет внешние математические операции над метрологическими сущностями"""

    @staticmethod
    def concatenate_grids(traces: list) -> tuple:
        """
        ВЫСОКОЭФФЕКТИВНОЕ СОЕДИНЕНИЕ СЕТОК ЧАСТОТ (O(N)):
        Собирает частотные оси всех объектов, выполняет сортировку и удаление
        дубликатов ОДИН раз в конце, сохраняя исходную длину кортежа для распаковки.
        """
        if not traces:
            return ()

        # 1. Фильтруем входящий список, оставляя только реальные объекты Trace/Uncertainty
        clean_traces = [t for t in traces if t is not None]

        # 🌟 ИСПРАВЛЕНИЕ: Если вообще все переданные объекты были None,
        # возвращаем кортеж из None ТОЙ ЖЕ ДЛИНЫ, что и входящий список!
        if not clean_traces:
            return tuple(None for _ in traces)

        # 2. Собираем абсолютно все частоты в единый массив ("кучу")
        raw_frequencies_pool = []
        for current_trace in clean_traces:
            if current_trace.frequencies_units.lower() != 'hz':
                from src.core.math_models import FrequencyConverter
                ratio = FrequencyConverter.get_ratio(from_unit=current_trace.frequencies_units, to_unit='Hz')
                raw_frequencies_pool.append(current_trace.frequencies * ratio)
            else:
                raw_frequencies_pool.append(current_trace.frequencies)

        combined_pool = np.concatenate(raw_frequencies_pool)

        # 3. Очистка от дубликатов и сортировка строго ОДИН раз
        union_grid_hz = np.sort(np.unique(combined_pool))

        # 4. Перестраиваем под общую сетку только те объекты, которые реально существовали.
        # Для объектов, которые были None, возвращаем None, ЖЕСТКО сохраняя порядок и длину!
        result = []
        for original_trace in traces:
            if original_trace is not None:
                result.append(original_trace.align_to_grid(union_grid_hz))
            else:
                result.append(None)

        return tuple(result)


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
            return traces[0]  # Исправленный нами ранее индекс 0
        all_freqs = np.concatenate([t.frequencies for t in traces])
        all_values = np.concatenate([t.values for t in traces])
        sort_indices = np.argsort(all_freqs, kind='mergesort')
        return Trace(frequencies=all_freqs[sort_indices], values=all_values[sort_indices],
                     frequencies_units=traces[0].frequencies_units, values_units=traces[0].values_units)