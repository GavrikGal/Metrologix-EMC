# src/core/budget_calculator.py
import numpy as np
from src.core.task_context import TaskContext
from src.core.measurement_chain import MeasurementChain


class CISPRBudgetCalculator:
    """Выполняет чистый математический расчет инструментального бюджета по СИСПР 16-4-2"""

    @staticmethod
    def calculate_emc_budget(context: TaskContext, chain: MeasurementChain) -> list:
        budget_comp = context.config.get('budget_composition', [])
        calculated_rows = []

        # Создаем плотную сетку частот для поиска максимума погрешности внутри полосы задачи
        test_frequencies = np.linspace(context.f_min_hz, context.f_max_hz, num=200)

        for item in budget_comp:
            device_role = item.get('device_role')
            param_name = item.get('target_parameter')
            device = chain.get_device(device_role)

            if not device or param_name not in device.processed_parameters:
                continue

            parameter = device.processed_parameters[param_name]

            if parameter.uncertainty_trace:
                interp_raw_uncertainties = parameter.uncertainty_trace.get_values_for_frequencies(test_frequencies)
                interp_std_uncertainties = parameter.uncertainty_trace.get_standard_uncertainty_for_frequencies(
                    test_frequencies)

                max_u_raw = np.max(interp_raw_uncertainties)
                u_std_val = np.max(interp_std_uncertainties)

                # Приводим к верхнему регистру для надежности сравнения
                dist_type = parameter.uncertainty_trace.distribution_type.upper()

                # 🌟 ИСПРАВЛЕНИЕ: Сравниваем строго в верхнем регистре "NORMAL"
                if dist_type == 'NORMAL':
                    k_val = parameter.uncertainty_trace.k_factor

                    if k_val is not None:
                        # Убираем дробную часть у целых чисел (2.0 -> 2)
                        k_str = f"{int(k_val)}" if float(k_val).is_integer() else f"{k_val}"
                        dist_str = f"NORMAL (k = {k_str})"
                    else:
                        dist_str = "NORMAL (k = 2)"  # Безопасный метрологический дефолт по CISPR
                else:
                    dist_str = dist_type
            else:
                max_u_raw, u_std_val, dist_str = 0.0, 0.0, "NONE"

            # 🌟 ИСПРАВЛЕНИЕ: Передаем именно нашу сформированную строку dist_str в отчет
            calculated_rows.append({
                'name': item.get('component_name'),
                'device': f"{device.name} [{device_role}]",
                'raw_val': round(float(max_u_raw), 4),
                'dist': dist_str,  # <--- ТЕПЕРЬ ЗДЕСЬ ПРАВИЛЬНАЯ СТРОКА С (k)
                'u_std': round(float(u_std_val), 4)
            })

        return calculated_rows
