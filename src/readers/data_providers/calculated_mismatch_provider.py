# src/readers/data_providers/calculated_mismatch_provider.py
import logging
import numpy as np
from .base_provider import BaseDataProvider
from src.core.data_structures.parameter import Parameter
from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty
from src.core.utils.trace_manipulator import TraceManipulator

logger = logging.getLogger("Metrologix")


class CalculatedMismatchProvider(BaseDataProvider):
    """Провайдер динамического расчета неопределенности рассогласования (delta M) на базе S-параметров"""

    @staticmethod
    def _vswr_to_gamma(vswr_values: np.ndarray) -> np.ndarray:
        """Перевод КСВН (SWR) в модуль коэффициента отражения |Gamma|"""
        vswr_clipped = np.clip(vswr_values, 1.0, None)
        return (vswr_clipped - 1.0) / (vswr_clipped + 1.0)

    @staticmethod
    def _db_loss_to_linear_s21(db_values: np.ndarray) -> np.ndarray:
        """Перевод затухания S21 из дБ в линейный масштаб коэффициента передачи (в разы)"""
        return 10 ** (-np.abs(db_values) / 20.0)

    def get_parameter(self) -> Parameter:
        logger.info("Запуск синтеза параметра рассогласования тракта по S-параметрам...")

        # 1. Извлекаем трассы из конфигурации
        source_vswr_trace = self.config.get('source_vswr_trace')  # КСВН ЭСП (LISN)
        load_vswr_trace = self.config.get('load_vswr_trace')  # КСВН Приемника

        cable_s21_trace = self.config.get('cable_s21_trace')  # Коэффициент передачи кабеля (S21)
        cable_s11_trace = self.config.get('cable_s11_trace')  # Коэффициент отражения входа (S11)
        cable_s22_trace = self.config.get('cable_s22_trace')  # Коэффициент отражения выхода (S22)

        if not (source_vswr_trace and load_vswr_trace and cable_s21_trace):
            raise ValueError("[MismatchProvider] Отсутствуют критические S-параметры/КСВН для расчета рассогласования!")

        # 2. МЕТРОЛОГИЧЕСКОЕ СОЕДИНЕНИЕ СЕТОК ЧАСТОТ ЧЕРЕЗ ЧЕРНЫЙ ЯЩИК
        _, aligned_load = TraceManipulator.concatenate_grids(source_vswr_trace, load_vswr_trace)
        calculation_grid = aligned_load.frequencies

        # Ленивая интерполяция всех участников на единый расчетный базис частот задачи
        vswr_source = source_vswr_trace.get_values_for_frequencies(calculation_grid)
        vswr_load = load_vswr_trace.get_values_for_frequencies(calculation_grid)
        loss_cable_db = cable_s21_trace.get_values_for_frequencies(calculation_grid)

        # Обработка КСВН кабеля S11/S22 (если не заданы в паспорте — метрологически принимаем дефолт 1.2)
        vswr_cable_in = cable_s11_trace.get_values_for_frequencies(
            calculation_grid) if cable_s11_trace else np.full_like(calculation_grid, 1.2)
        vswr_cable_out = cable_s22_trace.get_values_for_frequencies(
            calculation_grid) if cable_s22_trace else np.full_like(calculation_grid, 1.2)

        # 3. МАТЕМАТИЧЕСКИЙ ПЕРЕВОД В ЛИНЕЙНЫЕ МОДУЛИ КОЭФФИЦИЕНТОВ МАТРИЦЫ РАССЕЯНИЯ
        gamma_g = self._vswr_to_gamma(vswr_source)  # |Gamma_source|
        gamma_l = self._vswr_to_gamma(vswr_load)  # |Gamma_load|
        s11 = self._vswr_to_gamma(vswr_cable_in)  # |S11| модуля отражения
        s22 = self._vswr_to_gamma(vswr_cable_out)  # |S22| модуля отражения
        s21 = self._db_loss_to_linear_s21(loss_cable_db)  # |S21| в разах

        # 4. ВЫЧИСЛЕНИЕ ГРАНИЦ ПО ФОРМУЛЕ ГОСТ CISPR 16-4-2 (Покоординатно для СВЧ тракта)
        rss_sum = (gamma_g * s11) ** 2 + (gamma_l * s22) ** 2 + (gamma_g * gamma_l * s21) ** 2
        calculated_mismatch_limits = 8.7 * np.sqrt(rss_sum)

        # 5. СИНТЕЗ ПАРАМЕТРА ДЛЯ ДВИЖКА
        final_value_trace = Trace(calculation_grid, np.zeros_like(calculation_grid))
        final_uncertainty_trace = Uncertainty(
            frequencies=calculation_grid,
            values=calculated_mismatch_limits,
            distribution_type='u_shaped'  # Делитель sqrt(2)
        )

        logger.info(f"Расчет рассогласования по S-параметрам завершен. Точек: {len(calculation_grid)}, "
                    f"Максимальный вклад погрешности: ±{calculated_mismatch_limits.max():.4f} дБ")

        return Parameter(final_value_trace, final_uncertainty_trace)
