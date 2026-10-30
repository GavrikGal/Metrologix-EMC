# src/reports/renderers/plot_renderer.py
import logging
import os
import matplotlib.pyplot as plt
import numpy as np

from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty
from src.reports.base_renderer import BaseRenderer
from src.core.math_models import FrequencyConverter
from src.reports.utils.name_builder import NameBuilder

logger = logging.getLogger("Metrologix")


class PlotRenderer(BaseRenderer):
    """Компонент отрисовки спектральных графиков Matplotlib с поддержкой кастомизации"""

    def __init__(self, visualizer_setup: dict):
        self.default_plots_config = visualizer_setup.get("plots_settings", {})
        self.default_style_config = visualizer_setup.get("style_settings", {})

    def render(self, output_dir: str, device_config: dict, param_name: str,
               values: Trace, uncertainty: Uncertainty, sub_cfg: dict) -> None:
        """
        Шаблонный метод отрисовки графического отчета.
        Координирует вызовы специализированных микро-методов.
        """
        # Подготовка масштабированных частот
        freqs_hz = values.frequencies
        target_unit = sub_cfg.get('unit', self.default_plots_config.get('unit', 'MHz'))
        ratio = FrequencyConverter.get_ratio(from_unit="Hz", to_unit=target_unit)
        freqs_scaled = freqs_hz * ratio

        f_min_spec = float(sub_cfg.get('freq_min', freqs_scaled.min()))
        f_max_spec = float(sub_cfg.get('freq_max', freqs_scaled.max()))

        # Получение стилей (динамический fallback)
        st = sub_cfg.get('style_settings', {})

        def style_provider(key: str):
            return st.get(key, self.default_style_config.get(key))

        # Инициализация окна графика
        plt.figure(figsize=(10, 5))

        # Последовательная пошаговая сборка слоев графика
        self._draw_main_trace(values, target_unit, device_config, style_provider)
        self._draw_uncertainty_corridor(values, uncertainty, target_unit, style_provider)
        self._draw_limit_line(sub_cfg, style_provider)

        # Фиксируем границы окна Matplotlib перед наложением масок
        plt_x_min, plt_x_max = plt.xlim()
        self._draw_shading_zones(plt_x_min, plt_x_max, f_min_spec, f_max_spec, style_provider)

        # todo: в аннотациях (из-за большего количества точке на графике) вычисляется и отображается не тот же максимум, что в таблице для протокола
        # self._draw_maximum_uncertainty_annotation(values, uncertainty, target_unit, f_min_spec, f_max_spec)
        self._apply_grid_and_axes_settings(sub_cfg, target_unit, param_name, plt_x_min, plt_x_max)

        # Сохранение готового файла
        filename = NameBuilder.build_standard_filename(device_config, freqs_hz.min(), freqs_hz.max(),
                                                       ".png", param_name=param_name)
        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(os.path.join(output_dir, filename), dpi=200, bbox_inches='tight')
        logger.info(f'Создан график: {filename}')
        plt.close()


    # =========================================================================
    # МИКРО-МЕТОДЫ ОТРИСОВКИ СЛОЕВ (САМОДОКУМЕНТИРУЕМЫЙ КОД)
    # =========================================================================

    # def _draw_main_trace(self, x: np.ndarray, y: np.ndarray, dev_config: dict, style) -> None:
    @staticmethod
    def _draw_main_trace(values: Trace, freq_unit: str, dev_config: dict, style) -> None:
        """Отрисовка основной спектральной линии прибора"""
        y = values.values
        x = values.frequencies

        # Конвертация единиц измерения частоты, для которых хранятся данные, в запрашиваемые
        ratio = FrequencyConverter.get_ratio(from_unit="Hz", to_unit=freq_unit)
        x_scaled = x * ratio

        label_id = dev_config.get('device_short_id', 'Device')
        plt.plot(x_scaled, y, label=label_id, color=style('line_color'), lw=style('line_width'), zorder=3)


    @staticmethod
    def _draw_uncertainty_corridor(values: Trace, uncertainty: Uncertainty, freq_unit: str, style) -> None:
        """Отрисовка полупрозрачного коридора расширенной неопределенности k=2"""
        # В значения (values) неопределенности (Uncertainty) хранится расширенная неопределенность
        y = values.values
        u_expanded = uncertainty.values
        x = values.frequencies

        # Конвертация единиц измерения частоты, для которых хранятся данные, в запрашиваемые
        ratio = FrequencyConverter.get_ratio(from_unit="Hz", to_unit=freq_unit)
        x_scaled = x * ratio

        line_w = style('line_width') / 2 if style('line_width') else 0.5
        plt.fill_between(x_scaled, y - u_expanded, y + u_expanded,
                         color=style('uncertainty_color'), alpha=style('uncertainty_alpha'),
                         lw=line_w, label='Расширенная неопределенность (k=2)', zorder=2)


    def _draw_limit_line(self, sub_cfg: dict, style) -> None:
        """Отрисовка горизонтальной линии допуска/лимита CISPR"""
        show_limit = sub_cfg.get('show_limit_line', self.default_plots_config.get('show_limit_line', False))
        if show_limit:
            limit_val = sub_cfg.get('limit_value_db', self.default_plots_config.get('limit_value_db', 0.0))
            plt.axhline(y=limit_val, color=style('limit_color'), linestyle=style('limit_style'),
                        lw=style('limit_width'), label='Лимит', zorder=4)


    @staticmethod
    def _draw_shading_zones(x_min: float, x_max: float, f_min: float, f_max: float, style) -> None:
        """Метрологическое затемнение нерабочих частотных областей за границами спецификации"""
        color = style('shading_color')
        alpha = style('shading_alpha')
        if x_min < f_min:
            plt.axvspan(x_min, f_min, color=color, alpha=alpha, zorder=1)
        if x_max > f_max:
            plt.axvspan(f_max, x_max, color=color, alpha=alpha, zorder=1)

    @staticmethod
    def _draw_maximum_uncertainty_annotation(values: Trace, uncertainty: Uncertainty, freq_unit: str,
                                             f_min: float, f_max: float) -> None:
        """Поиск наихудшей метрологической точки и вывод стрелки-выноски с её параметрами"""
        # В значения (values) неопределенности (Uncertainty) хранится расширенная неопределенность
        y = values.values
        u_expanded = uncertainty.values
        x = values.frequencies

        # Конвертация единиц измерения частоты, для которых хранятся данные, в запрашиваемые
        ratio = FrequencyConverter.get_ratio(from_unit="Hz", to_unit=freq_unit)
        x_scaled = x * ratio
        mask = (x_scaled >= f_min) & (x_scaled <= f_max)

        if np.any(mask):
            u_zone, f_zone, v_zone = u_expanded[mask], x_scaled[mask], y[mask]
            m_idx = np.argmax(u_zone)

            # Ставим черную точку на максимуме
            plt.scatter(f_zone[m_idx], v_zone[m_idx], color='black', s=6, zorder=5)

            # Текст и геометрия стрелки выноски
            text = f"F={f_zone[m_idx]:.3f}\nMax={u_zone[m_idx]:.3f}"

            # Получаем текущие границы оси Y, чтобы определить, где находится точка
            y_min, y_max = plt.ylim()
            y_range = abs(y_max - y_min)

            # Проверяем, находится ли точка в верхней четверти (для S21 значения отрицательные, поэтому y_max — это верх)
            is_in_top_quarter = v_zone[m_idx] > (y_max - 0.25 * y_range)

            if is_in_top_quarter:
                # Точка вверху: смещаем текст ВЛЕВО (стрелка выходит из правой боковой стороны блока)
                # Если точка слишком близко к левому краю, можно изменить на 50 (вправо)
                x_offset = -60 if f_zone[m_idx] > (plt.xlim()[1] * 0.2) else 60
                y_offset = 0  # Строго по центру боковой стороны
                ha = 'right' if x_offset < 0 else 'left'
                va = 'center'
            else:
                # Точка ниже: смещаем текст ВВЕРХ (стрелка выходит строго снизу блока)
                x_offset = 0  # Строго по центру над точкой
                y_offset = 40  # Смещение вверх в пунктах
                ha = 'center'
                va = 'bottom'

            # Рисуем аннотацию
            plt.annotate(
                text,
                xy=(f_zone[m_idx], v_zone[m_idx]),
                xytext=(x_offset, y_offset),
                textcoords='offset points',  # Ключевой момент: смещение в пунктах, а не в координатах графика
                ha=ha,
                va=va,
                arrowprops=dict(
                    arrowstyle="->",
                    color="black",
                    lw=0.7,
                    # Простая прямая стрелка выглядит аккуратнее, но можно оставить и "angle"
                    connectionstyle="arc3,rad=0"
                ),
                bbox=dict(
                    boxstyle="round,pad=0.3,rounding_size=0.15",
                    fc="white",
                    edgecolor="lightgrey",
                    lw=0.7
                ),
                fontsize=9,
                zorder=6
            )

    def _apply_grid_and_axes_settings(self, sub_cfg: dict, unit: str, param_name: str, x_min: float,
                                      x_max: float) -> None:
        """Настройка масштабных сеток, логарифмических шкал и подписей осей"""
        scale_type = sub_cfg.get('x_scale', self.default_plots_config.get('x_scale', 'linear'))
        plt.xscale(scale_type)
        plt.xlim(x_min, x_max)

        # Основная и вспомогательная сетки
        plt.grid(True, which='major', ls="-", alpha=0.5, zorder=0, lw=0.3)
        plt.minorticks_on()
        plt.grid(True, which='minor', ls="-", alpha=0.3, zorder=0, lw=0.2)

        plt.title(sub_cfg.get('title', 'Plot'), fontsize=11, weight='bold')
        plt.xlabel(f'Частота, {unit}')
        plt.ylabel(f'{param_name}, dB')
        plt.legend(loc='upper right', frameon=True)
