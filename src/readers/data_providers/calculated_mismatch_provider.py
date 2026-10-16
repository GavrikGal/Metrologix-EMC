# src/readers/data_providers/calculated_mismatch_provider.py
import logging
import numpy as np
from .base_provider import BaseDataProvider
from src.core.data_structures.parameter import Parameter
from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty
from src.core.utils.trace_manipulator import TraceManipulator  # 🌟 Импортируем манипулятор

logger = logging.getLogger("Metrologix")


class CalculatedMismatchProvider(BaseDataProvider):
    """Провайдер динамического расчета неопределенности рассогласования (delta M) по СИСПР 16-4-2"""

    def get_parameter(self) -> Parameter:
        # 1. Извлекаем трассы из конфигурации, переданные Движком
        source_vswr_trace = self.config.get('source_vswr_trace')  # КСВН LISN / Аттенюатора (SWR)
        load_vswr_trace = self.config.get('load_vswr_trace')  # КСВН Приемника (SWR)

        cable_s21_trace = self.config.get('cable_s21_trace')  # Затухание кабеля S21 (dB)
        cable_s11_trace = self.config.get('cable_s11_trace')
        cable_s22_trace = self.config.get('cable_s22_trace')

        # 2. МЕТРОЛОГИЧЕСКИЙ ДЕФОЛТ ДЛЯ КСВН КАБЕЛЯ
        # Если КСВН входа/выхода кабеля отсутствуют в паспорте, создаем константы 1.2 на сетке S21
        f_min, f_max = cable_s21_trace.frequencies.min(), cable_s21_trace.frequencies.max()
        s11_src = cable_s11_trace if cable_s11_trace else Trace.create_constant(f_min, f_max, 1.2, values_units='SWR')
        s22_src = cable_s22_trace if cable_s22_trace else Trace.create_constant(f_min, f_max, 1.2, values_units='SWR')

        # 3. 🌟 ЕДИНОВРЕМЕННОЕ ВЫРАВНИВАНИЕ ВСЕХ СЕТОК ЧАСТОТ КАСКАДА (O(N))
        # Закидываем все 5 трасс в наш манипулятор. Он соединит их оси и вернет кортеж идеально выровненных объектов!
        aligned_source, aligned_load, aligned_s21, aligned_s11, aligned_s22 = TraceManipulator.concatenate_grids([
            source_vswr_trace,
            load_vswr_trace,
            cable_s21_trace,
            s11_src,
            s22_src
        ])

        # 4. РАДИОТЕХНИЧЕСКАЯ КОНВЕРТАЦИЯ ШКАЛ НА ЕДИНОЙ СЕТКЕ FREQUENCIES
        gamma_g = aligned_source.swr_to_gamma()  # Модуль отражения источника
        gamma_l = aligned_load.swr_to_gamma()  # Модуль отражения нагрузки
        s11_lin = aligned_s11.swr_to_gamma()  # Модуль отражения входа кабеля
        s22_lin = aligned_s22.swr_to_gamma()  # Модуль отражения выхода кабеля
        s21_lin = aligned_s21.to_linear()  # Коэффициент передачи кабеля в разах

        # 5. ВЫЧИСЛЕНИЕ ФОРМУЛЫ СИСПР НА БЕЗОПАСНЫХ ОДНОМЕРНЫХ МАССИВАХ
        # Так как сетки частот объектов теперь на 100% идентичны, умножение и сложение пройдут без ошибок shapes
        comp_1 = gamma_g * s11_lin
        comp_2 = gamma_l * s22_lin
        comp_3 = gamma_g * gamma_l * s21_lin

        # Покоординатно собираем сумму квадратов переотражений
        rss_sum_values = (comp_1.values) ** 2 + (comp_2.values) ** 2 + (comp_3.values) ** 2
        calculated_mismatch_limits = 8.7 * np.sqrt(rss_sum_values)

        # 6. СИНТЕЗ ПАРАМЕТРА ДЛЯ ДВИЖКА
        calculation_grid = gamma_g.frequencies
        final_value_trace = Trace(calculation_grid, np.zeros_like(calculation_grid), values_units='dB')
        final_uncertainty_trace = Uncertainty(
            frequencies=calculation_grid,
            values=calculated_mismatch_limits,
            values_units='dB',
            distribution_type='u_shaped'
        )

        param_name = self.config.get('parameter_system_name', 'Tract_Mismatch')
        return Parameter(param_name, final_value_trace, final_uncertainty_trace)
