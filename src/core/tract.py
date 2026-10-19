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
    """Виртуальная модель СВЧ-тракта. Вычисляет каскадный Mismatch по матрицам рассеяния"""

    def __init__(self, task: Task, hardware: Hardware) -> None:
        self.task = task
        self.hardware = hardware
        self.cfg = task.config.get('tract_cascade', {})

    def calculate_total_mismatch(self) -> Parameter:
        if not self.cfg:
            grid = np.array([self.task.frequency_min_hz, self.task.frequency_max_hz])
            return Parameter("Tract_Mismatch", Trace(grid, np.zeros_like(grid)),
                             Uncertainty(grid, np.zeros_like(grid), distribution_type='u_shaped'))

        source_role = self.cfg.get('source', 'lisn')
        load_role = self.cfg.get('load', 'receiver')
        cascade_roles = self.cfg.get('cascade', ['attenuator', 'cable_system'])

        chain_roles = [source_role] + cascade_roles + [load_role]
        chain_devices = [self.hardware.get_device(role) for role in chain_roles if self.hardware.get_device(role)]

        traces_to_merge = []
        for dev in chain_devices:
            if 'LISN_VSWR' in dev.processed_parameters:
                traces_to_merge.append(dev.processed_parameters['LISN_VSWR'].value_trace)
            elif 'Receiver_VSWR' in dev.processed_parameters:
                traces_to_merge.append(dev.processed_parameters['Receiver_VSWR'].value_trace)
            elif 'S21' in dev.processed_parameters:
                traces_to_merge.append(dev.processed_parameters['S21'].value_trace)

        aligned_result = TraceManipulator.concatenate_grids(traces_to_merge)
        task_grid_hz = aligned_result[0].frequencies

        mask = (task_grid_hz >= self.task.frequency_min_hz) & (task_grid_hz <= self.task.frequency_max_hz)
        final_grid_hz = task_grid_hz[mask] if np.any(mask) else np.array(
            [self.task.frequency_min_hz, self.task.frequency_max_hz])

        nodes = []
        for dev in chain_devices:
            if 'Receiver_VSWR' in dev.processed_parameters:
                vswr_in = dev.processed_parameters['Receiver_VSWR'].value_trace.get_values_for_frequencies(
                    final_grid_hz)
            elif 'S11' in dev.processed_parameters:
                vswr_in = dev.processed_parameters['S11'].value_trace.get_values_for_frequencies(final_grid_hz)
            else:
                vswr_in = np.full_like(final_grid_hz, 1.2)

            if 'LISN_VSWR' in dev.processed_parameters:
                vswr_out = dev.processed_parameters['LISN_VSWR'].value_trace.get_values_for_frequencies(final_grid_hz)
            elif 'S22' in dev.processed_parameters:
                vswr_out = dev.processed_parameters['S22'].value_trace.get_values_for_frequencies(final_grid_hz)
            else:
                vswr_out = np.full_like(final_grid_hz, 1.2)

            s21_db = dev.processed_parameters['S21'].value_trace.get_values_for_frequencies(
                final_grid_hz) if 'S21' in dev.processed_parameters else np.zeros_like(final_grid_hz)

            gamma_in = (vswr_in - 1.0) / (vswr_in + 1.0)
            gamma_out = (vswr_out - 1.0) / (vswr_out + 1.0)

            # Перевод знака для логарифмического затухания
            s21_db_signed = -np.abs(
                s21_db) if 'cable' in dev.name.lower() or 'attenuator' in dev.name.lower() else s21_db
            s21_lin = 10 ** (s21_db_signed / 20.0)

            nodes.append({'in': gamma_in, 'out': gamma_out, 's21': s21_lin})

        # Сквозное каскадирование S-матриц
        gamma_source = nodes[0]['out']
        gamma_load = nodes[-1]['in']

        middle_elements = nodes[1:-1]
        equivalent_s11 = np.copy(middle_elements[0]['in'])
        equivalent_s22 = np.copy(middle_elements[0]['out'])
        equivalent_s21 = np.copy(middle_elements[0]['s21'])

        for next_elem in middle_elements[1:]:
            denom = 1.0 - equivalent_s22 * next_elem['in']
            equivalent_s11 = equivalent_s11 + (equivalent_s21 * next_elem['in'] * equivalent_s21) / denom
            equivalent_s22 = next_elem['out'] + (next_elem['s21'] * equivalent_s22 * next_elem['s21']) / denom
            equivalent_s21 = (equivalent_s21 * next_elem['s21']) / denom

        # Формула СИСПР 16-4-2
        v1 = gamma_source * equivalent_s11
        v2 = gamma_load * equivalent_s22
        v3 = gamma_source * gamma_load * equivalent_s21

        mismatch_component = (v1) ** 2 + (v2) ** 2 + (v3) ** 2
        final_limits = 8.7 * np.sqrt(mismatch_component)

        v_trace = Trace(final_grid_hz, np.zeros_like(final_grid_hz), values_units='dB')
        u_trace = Uncertainty(final_grid_hz, final_limits, values_units='dB', distribution_type='u_shaped')

        logger.info(f"[Tract] Расчет рассогласования каскада завершен успешно. Элементов: {len(nodes)}")
        return Parameter("Tract_Mismatch", v_trace, u_trace)
