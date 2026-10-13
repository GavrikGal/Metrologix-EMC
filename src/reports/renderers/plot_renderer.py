# src/reports/renderers/plot_renderer.py
import os
import matplotlib.pyplot as plt
import numpy as np
from src.reports.base_renderer import BaseRenderer
from src.core.math_models import FrequencyConverter
from src.reports.utils.name_builder import NameBuilder


class PlotRenderer(BaseRenderer):
    """Компонент отрисовки спектральных графиков Matplotlib с поддержкой кастомизации"""

    def __init__(self, visualizer_setup: dict):
        self.default_plots_config = visualizer_setup.get("plots_settings", {})
        self.default_style_config = visualizer_setup.get("style_settings", {})

    def render(self, output_dir: str, device_config: dict, param_name: str,
               freqs_hz: np.ndarray, values: np.ndarray, u_std: np.ndarray, sub_cfg: dict) -> None:
        """
        Шаблонный метод отрисовки графического отчета.
        Координирует вызовы специализированных микро-методов.
        """
        # Подготовка масштабированных частот
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
        self._draw_main_trace(freqs_scaled, values, device_config, style_provider)
        self._draw_uncertainty_corridor(freqs_scaled, values, u_std, style_provider)
        self._draw_limit_line(sub_cfg, style_provider)

        # Фиксируем границы окна Matplotlib перед наложением масок
        plt_x_min, plt_x_max = plt.xlim()

        self._draw_shading_zones(plt_x_min, plt_x_max, f_min_spec, f_max_spec, style_provider)
        self._draw_maximum_uncertainty_annotation(freqs_scaled, values, u_std, f_min_spec, f_max_spec)
        self._apply_grid_and_axes_settings(sub_cfg, target_unit, param_name, plt_x_min, plt_x_max)

        # Сохранение готового файла
        filename = NameBuilder.build_standard_filename(device_config, freqs_hz.min(), freqs_hz.max(), ".png")
        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(os.path.join(output_dir, filename), dpi=200, bbox_inches='tight')
        plt.close()

    # =========================================================================
    # МИКРО-МЕТОДЫ ОТРИСОВКИ СЛОЕВ (САМОДОКУМЕНТИРУЕМЫЙ КОД)
    # =========================================================================

    def _draw_main_trace(self, x: np.ndarray, y: np.ndarray, dev_config: dict, style) -> None:
        """Отрисовка основной спектральной линии прибора"""
        label_id = dev_config.get('device_short_id', 'Device')
        plt.plot(x, y, label=label_id, color=style('line_color'), lw=style('line_width'), zorder=3)

    def _draw_uncertainty_corridor(self, x: np.ndarray, y: np.ndarray, u_std: np.ndarray, style) -> None:
        """Отрисовка полупрозрачного коридора расширенной неопределенности k=2"""
        u_expanded = u_std * 2
        line_w = style('line_width') / 2 if style('line_width') else 0.5
        plt.fill_between(x, y - u_expanded, y + u_expanded,
                         color=style('uncertainty_color'), alpha=style('uncertainty_alpha'),
                         lw=line_w, label='Неопределённость', zorder=2)

    def _draw_limit_line(self, sub_cfg: dict, style) -> None:
        """Отрисовка горизонтальной линии допуска/лимита CISPR"""
        show_limit = sub_cfg.get('show_limit_line', self.default_plots_config.get('show_limit_line', False))
        if show_limit:
            limit_val = sub_cfg.get('limit_value_db', self.default_plots_config.get('limit_value_db', 0.0))
            plt.axhline(y=limit_val, color=style('limit_color'), linestyle=style('limit_style'),
                        lw=style('limit_width'), label='Лимит', zorder=4)

    def _draw_shading_zones(self, x_min: float, x_max: float, f_min: float, f_max: float, style) -> None:
        """Метрологическое затемнение нерабочих частотных областей за границами спецификации"""
        color = style('shading_color')
        alpha = style('shading_alpha')
        if x_min < f_min:
            plt.axvspan(x_min, f_min, color=color, alpha=alpha, zorder=1)
        if x_max > f_max:
            plt.axvspan(f_max, x_max, color=color, alpha=alpha, zorder=1)

    def _draw_maximum_uncertainty_annotation(self, x: np.ndarray, y: np.ndarray, u_std: np.ndarray, f_min: float,
                                             f_max: float) -> None:
        """Поиск наихудшей метрологической точки и вывод стрелки-выноски с её параметрами"""
        u_expanded = u_std * 2
        mask = (x >= f_min) & (x <= f_max)

        if np.any(mask):
            u_zone, f_zone, v_zone = u_expanded[mask], x[mask], y[mask]
            m_idx = np.argmax(u_zone)

            # Ставим черную точку на максимуме
            plt.scatter(f_zone[m_idx], v_zone[m_idx], color='black', s=6, zorder=5)

            # Текст и геометрия стрелки выноски
            text = f"F={f_zone[m_idx]:.1f}\nMax={u_zone[m_idx]:.2f}"
            y_min, _ = plt.ylim()
            y_text_pos = y_min - (y_min - v_zone[m_idx]) / 2
            x_text_pos = f_zone[m_idx] - (x.max() - x.min()) * 0.15

            plt.annotate(
                text, xy=(f_zone[m_idx], v_zone[m_idx]), xytext=(x_text_pos, y_text_pos),
                arrowprops=dict(arrowstyle="->", color="black", lw=0.7,
                                connectionstyle="angle,angleA=0,angleB=90,rad=5"),
                bbox=dict(boxstyle="round,pad=0.2,rounding_size=0.15", fc="white", edgecolor="lightgrey", lw=0.7),
                fontsize=9, zorder=6
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
