# src/reports/renderers/plot_renderer.py
import os
import matplotlib.pyplot as plt
import numpy as np
from src.core.math_models import FrequencyConverter
from src.reports.utils.name_builder import NameBuilder


class PlotRenderer:
    """Компонент отрисовки спектральных графиков Matplotlib с поддержкой кастомизации"""

    def __init__(self, visualizer_setup: dict):
        self.default_plots_config = visualizer_setup.get("plots_settings", {})
        self.default_style_config = visualizer_setup.get("style_settings", {})

    def render(self, output_dir: str, device_config: dict, param_name: str,
               freqs_hz: np.ndarray, values: np.ndarray, u_std: np.ndarray, sub_cfg: dict):

        target_unit = sub_cfg.get('unit', self.default_plots_config.get('unit', 'MHz'))
        ratio = FrequencyConverter.get_ratio(from_unit="Hz", to_unit=target_unit)
        freqs_scaled = freqs_hz * ratio

        f_min_spec = float(sub_cfg.get('freq_min', freqs_scaled.min()))
        f_max_spec = float(sub_cfg.get('freq_max', freqs_scaled.max()))
        st = sub_cfg.get('style_settings', {})

        def get_style(key: str):
            return st.get(key, self.default_style_config.get(key))

        plt.figure(figsize=(10, 5))

        # 1. Основная линия прибора
        plt.plot(freqs_scaled, values, label=device_config.get('device_short_id', 'Device'),
                 color=get_style('line_color'), lw=get_style('line_width'), zorder=3)

        # 2. Коридор погрешности k=2
        u_expanded = u_std * 2
        plt.fill_between(freqs_scaled, values - u_expanded, values + u_expanded,
                         color=get_style('uncertainty_color'), alpha=get_style('uncertainty_alpha'),
                         lw=get_style('line_width') / 2 if get_style('line_width') else 0.5,
                         label='Неопределённость', zorder=2)

        # 3. Линия лимита
        if sub_cfg.get('show_limit_line', self.default_plots_config.get('show_limit_line', False)):
            plt.axhline(y=sub_cfg.get('limit_value_db', self.default_plots_config.get('limit_value_db', 0.0)),
                        color=get_style('limit_color'), linestyle=get_style('limit_style'),
                        lw=get_style('limit_width'), label='Лимит', zorder=4)

        # 🌟 ИСПРАВЛЕНИЕ 1: Честное извлечение текущих границ графического окна по оси X
        plt_x_min, plt_x_max = plt.xlim()

        # 4. Затемнение нерабочих областей
        if plt_x_min < f_min_spec:
            plt.axvspan(plt_x_min, f_min_spec, color=get_style('shading_color'), alpha=get_style('shading_alpha'),
                        zorder=1)
        if plt_x_max > f_max_spec:
            plt.axvspan(f_max_spec, plt_x_max, color=get_style('shading_color'), alpha=get_style('shading_alpha'),
                        zorder=1)

        # 5. Аннотация максимума неопределенности
        mask = (freqs_scaled >= f_min_spec) & (freqs_scaled <= f_max_spec)
        if np.any(mask):
            u_zone, f_zone, v_zone = u_expanded[mask], freqs_scaled[mask], values[mask]
            m_idx = np.argmax(u_zone)
            plt.scatter(f_zone[m_idx], v_zone[m_idx], color='black', s=6, zorder=5)

            annotation_text = f"F={f_zone[m_idx]:.1f}\nMax={u_zone[m_idx]:.2f}"

            # 🌟 ИСПРАВЛЕНИЕ 2: Честное извлечение нижней границы оси Y (из кортежа ylim)
            plt_y_min, _ = plt.ylim()

            plt.annotate(
                annotation_text,
                xy=(f_zone[m_idx], v_zone[m_idx]),
                xytext=(f_zone[m_idx] - (freqs_scaled.max() - freqs_scaled.min()) * 0.15,
                        plt_y_min - (plt_y_min - v_zone[m_idx]) / 2),
                arrowprops=dict(arrowstyle="->", color="black", lw=0.7,
                                connectionstyle="angle,angleA=0,angleB=90,rad=5"),
                bbox=dict(boxstyle="round,pad=0.2,rounding_size=0.15", fc="white", edgecolor="lightgrey", lw=0.7),
                fontsize=9,
                zorder=6
            )

        # Установка финальных параметров отображения спектрограммы
        plt.xscale(sub_cfg.get('x_scale', self.default_plots_config.get('x_scale', 'linear')))
        plt.xlim(plt_x_min, plt_x_max)
        plt.grid(True, which='major', ls="-", alpha=0.5, zorder=0, lw=0.3)
        plt.minorticks_on()
        plt.grid(True, which='minor', ls="-", alpha=0.3, zorder=0, lw=0.2)

        plt.title(sub_cfg.get('title', 'Plot'), fontsize=11, weight='bold')
        plt.xlabel(f'Частота, {target_unit}')
        plt.ylabel(f'{param_name}, dB')
        plt.legend(loc='upper right', frameon=True)

        filename = NameBuilder.build_standard_filename(device_config, freqs_hz.min(), freqs_hz.max(), ".png")
        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(os.path.join(output_dir, filename), dpi=200, bbox_inches='tight')
        plt.close()
