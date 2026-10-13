# src/core/budget_calculator.py
from src.core.task_context import TaskContext
from src.core.measurement_chain import MeasurementChain


class CISPRBudgetCalculator:
    """Выполняет чистый математический расчет инструментального бюджета по СИСПР 16-4-2"""

    @staticmethod
    def calculate_emc_budget(context: TaskContext, chain: MeasurementChain) -> list:
        budget_comp = context.config.get('budget_composition', [])
        calculated_rows = []

        for item in budget_comp:
            device_role = item.get('device_role')
            param_name = item.get('target_parameter')
            device = chain.get_device(device_role)

            if not device or param_name not in device.processed_parameters:
                continue

            parameter = device.processed_parameters[param_name]

            # 🌟 ДЕЛЕГИРОВАНИЕ: Неопределенность сама считает свои максимумы в диапазоне задачи
            if parameter.uncertainty_trace:
                max_u_raw, u_std_val = parameter.uncertainty_trace.get_max_uncertainties_in_range(
                    context.f_min_hz, context.f_max_hz
                )

                dist_type = parameter.uncertainty_trace.distribution_type.upper()
                if dist_type == 'NORMAL':
                    k_val = parameter.uncertainty_trace.k_factor
                    k_str = f"{int(k_val)}" if float(k_val).is_integer() else f"{k_val}"
                    dist_str = f"NORMAL (k = {k_str})"
                else:
                    dist_str = dist_type
            else:
                max_u_raw, u_std_val, dist_str = 0.0, 0.0, "NONE"

            calculated_rows.append({
                'name': item.get('component_name'),
                'device': f"{device.name} [{device_role}]",
                'raw_val': round(max_u_raw, 4),
                'dist': dist_str,
                'u_std': round(u_std_val, 4)
            })

        return calculated_rows
