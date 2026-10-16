# src/core/tract.py
import logging
import numpy as np
from src.core.task import Task
from src.core.hardware import Hardware
from src.core.data_structures.parameter import Parameter
from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty
from src.core.utils.trace_manipulator import TraceManipulator

logger = logging.getLogger("Metrologix")


class Tract:
    """Виртуальная модель СВЧ-тракта. Вычисляет каскадный Mismatch на операторах матриц рассеяния"""

    def __init__(self, task: Task, hardware: Hardware) -> None:
        self.task = task
        self.hardware = hardware
        self.cfg = task.config.get('tract_cascade', {})

    def calculate_total_mismatch(self) -> Parameter:
        if not self.cfg:
            grid = np.array([self.task.frequency_min_hz, self.task.frequency_max_hz])
            return Parameter("Tract_Mismatch", Trace(grid, np.zeros_like(grid)),
                             Uncertainty(grid, np.zeros_like(grid), distribution_type='u_shaped'))

        # 1. Собираем каскадную цепочку приборов от источника к нагрузке
        source_dev = self.hardware.get_device(self.cfg.get('source', 'lisn'))
        load_dev = self.hardware.get_device(self.cfg.get('load', 'receiver'))
        cascade_roles = self.cfg.get('cascade', ['attenuator', 'cable_system'])

        # 2. Объединяем оригинальные сетки частот участников, чтобы зафиксировать экстремумы задачи
        traces_to_merge = [source_dev.processed_parameters['LISN_VSWR'].value_trace]
        for role in cascade_roles:
            dev = self.hardware.get_device(role)
            if dev and 'S21' in dev.processed_parameters:
                traces_to_merge.append(dev.processed_parameters['S21'].value_trace)
        traces_to_merge.append(load_dev.processed_parameters['Receiver_VSWR'].value_trace)

        # Вызываем наш O(N) манипулятор сеток
        aligned_result = TraceManipulator.concatenate_grids(traces_to_merge)

        # 🌟 ИСПРАВЛЕНИЕ 1: Извлекаем из возвращенного кортежа первый элемент [0]
        task_grid_hz = aligned_result[0].frequencies

        # Вырезаем срез частот, строго попавших в измерительный диапазон таски
        mask = (task_grid_hz >= self.task.frequency_min_hz) & (task_grid_hz <= self.task.frequency_max_hz)
        final_grid_hz = task_grid_hz[mask] if np.any(mask) else np.array(
            [self.task.frequency_min_hz, self.task.frequency_max_hz])

        total_mismatch_variance = np.zeros_like(final_grid_hz)
        nodes = []

        # 3. Наполняем узлы схемы S-параметрами, ЖЕСТКО ВЫРОВНЕННЫМИ на единую частотную ось задачи
        chain_roles = [self.cfg.get('source', 'lisn')] + cascade_roles + [self.cfg.get('load', 'receiver')]
        for role in chain_roles:
            dev = self.hardware.get_device(role)

            # Лениво интерполируем КСВН портов на сетку задачи
            if 'Receiver_VSWR' in dev.processed_parameters:
                vswr_in = dev.processed_parameters['Receiver_VSWR'].value_trace.align_to_grid(final_grid_hz)
            elif 'S11' in dev.processed_parameters:
                vswr_in = dev.processed_parameters['S11'].value_trace.align_to_grid(final_grid_hz)
            else:
                vswr_in = Trace.create_constant(final_grid_hz.min(), final_grid_hz.max(), 1.2, values_units='SWR')

            if 'LISN_VSWR' in dev.processed_parameters:
                vswr_out = dev.processed_parameters['LISN_VSWR'].value_trace.align_to_grid(final_grid_hz)
            elif 'S22' in dev.processed_parameters:
                vswr_out = dev.processed_parameters['S22'].value_trace.align_to_grid(final_grid_hz)
            else:
                vswr_out = Trace.create_constant(final_grid_hz.min(), final_grid_hz.max(), 1.2, values_units='SWR')

            s21_trace = dev.processed_parameters['S21'].value_trace.align_to_grid(
                final_grid_hz) if 'S21' in dev.processed_parameters else Trace.create_constant(final_grid_hz.min(),
                                                                                               final_grid_hz.max(), 0.0,
                                                                                               values_units='dB')

            # Метрологическая конвертация: КСВН -> линейный порт отражения |Gamma|
            gamma_in_trace = vswr_in.swr_to_gamma()
            gamma_out_trace = vswr_out.swr_to_gamma()
            s21_linear_trace = s21_trace.to_linear()

            nodes.append({'in': gamma_in_trace, 'out': gamma_out_trace, 's21': s21_linear_trace})

            # 4. 🌟 БЕЗУПРЕЧНАЯ АЛГЕБРА СВЧ-ЦЕПЕЙ ПО СИСПР 16-4-2
            # Используем явный get_values_for_frequencies для извлечения массивов NumPy
            for i in range(len(nodes) - 1):
                gamma_g = nodes[i]['out']  # Выход левого разъема
                s11_next = nodes[i + 1]['in']  # Вход правого разъема
                s22_next = nodes[i + 1]['out']  # Выход правого разъема
                s21_next = nodes[i + 1]['s21']  # Линейная передача прибора

                gamma_l_next = nodes[i + 2]['in'] if i + 2 < len(nodes) else Trace.create_constant_on_grid(
                    final_grid_hz, 0.0, values_units='linear')

                # Физика взаимодействия портов на уровне иммутабельных операторов
                comp_1 = gamma_g * s11_next
                comp_2 = gamma_l_next * s22_next
                comp_3 = gamma_g * gamma_l_next * s21_next

                # 🌟 ИСПРАВЛЕНИЕ: Вместо прямого .values принудительно запрашиваем
                # значения строго на нашей единой системной сетке частот задачи!
                v1 = comp_1.get_values_for_frequencies(final_grid_hz)
                v2 = comp_2.get_values_for_frequencies(final_grid_hz)
                v3 = comp_3.get_values_for_frequencies(final_grid_hz)

                # Покоординатно собираем сумму квадратов переотражений на гарантированно одинаковых shape
                mismatch_component = (v1) ** 2 + (v2) ** 2 + (v3) ** 2
                total_mismatch_variance += (8.7 * np.sqrt(mismatch_component)) ** 2

            final_limits = np.sqrt(total_mismatch_variance)
            return Parameter("Tract_Mismatch", Trace(final_grid_hz, np.zeros_like(final_grid_hz)),
                             Uncertainty(final_grid_hz, final_limits, distribution_type='u_shaped'))
