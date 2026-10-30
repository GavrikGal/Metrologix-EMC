# src/core/budget_calculator.py
import numpy as np
from src.core.task import Task
from src.core.hardware import Hardware


class CISPRBudgetCalculator:
    """Выполняет чистый математический расчет инструментального бюджета по СИСПР 16-4-2"""

    @staticmethod
    def calculate_emc_budget(task: Task, hardware: Hardware) -> list:
        budget_components = task.config.get('budget_components', [])
        calculated_rows = []


        for item in budget_components:
            device_role = item.get('device_role')
            param_name = item.get('target_parameter')
            device = hardware.get_device(device_role)

            if not device or param_name not in device.processed_parameters:
                continue

            parameter = device.processed_parameters[param_name]

            if parameter.uncertainty_trace:
                # Делегирование: Неопределенность сама считает свои максимумы в диапазоне задачи
                # todo: Надо чтобы брались данные, которые выводились в таблицы протоколов
                max_u_raw, u_std_val = parameter.uncertainty_trace.get_max_uncertainties_in_range(
                    task.frequency_min_hz, task.frequency_max_hz
                )

                # 🌟 ИСПРАВЛЕНИЕ: Выбор текстовой метки для исходного значения
                if not parameter.uncertainty_trace.is_symmetric:
                    if max_u_raw > 0:
                        raw_value_display = f"+{max_u_raw:.2f} / 0.00"
                    else:
                        raw_value_display = 0.00
                else:
                    raw_value_display = round(max_u_raw, 4)

                dist_type = parameter.uncertainty_trace.distribution_type.upper()
                if dist_type == 'NORMAL':
                    k_val = parameter.uncertainty_trace.k_factor
                    k_str = f"{int(k_val)}" if float(k_val).is_integer() else f"{k_val}"
                    dist_str = f"NORMAL (k = {k_str})"
                else:
                    dist_str = dist_type
            else:
                raw_value_display, u_std_val, dist_str = 0.0, 0.0, "NONE"

            calculated_rows.append({
                'name': item.get('component_name'),
                'device': f"{device.name} [{device_role}]",
                'raw_val': raw_value_display,
                'dist': dist_str,
                'u_std': round(u_std_val, 4)
            })

        return calculated_rows
