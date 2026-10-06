# Файл: src/reports/visualizer.py
import os
import matplotlib.pyplot as plt
import numpy as np
from src.core.math_models import FrequencyConverter


class Visualizer:
    """Продвинутый графический движок системы Metrologix EMC с поддержкой глубокой кастомизации"""

    @staticmethod
    def _build_safe_title(device_type: str, short_id: str, sn: str, freq_range_str: str) -> str:
        """Формирует строгое информативное имя для файлов графиков и таблиц"""
        sn_part = f" №{sn}" if sn and sn != 'None' else ""
        full_title = f"{device_type}, {short_id}{sn_part} ({freq_range_str})"
        # for char in ['*', ':', '"', '<', '>', '|', '?', '(', ')']:
        #     full_title = full_title.replace(char, '')
        return full_title

    @staticmethod
    def draw_subplot(output_dir: str, device_config: dict, param_name: str,
                     freqs_hz: np.ndarray, values: np.ndarray, u_std: np.ndarray,
                     sub_cfg: dict, show_unc: bool = True):
        """Отрисовывает профессиональный кастомизированный спектральный график по референсу пользователя"""
        plots_dir = os.path.join(output_dir, "plots")
        os.makedirs(plots_dir, exist_ok=True)

        # 1. Считываем единицу измерения и масштабируем ось частот под данный конкретный график
        target_unit = sub_cfg.get('unit', 'MHz')
        ratio = FrequencyConverter.get_ratio(from_unit="Hz", to_unit=target_unit)
        freqs_scaled = freqs_hz * ratio

        # Границы исследуемого диапазона в выбранных пользователем единицах
        f_min_spec = float(sub_cfg.get('freq_min', freqs_scaled.min()))
        f_max_spec = float(sub_cfg.get('freq_max', freqs_scaled.max()))

        # Извлекаем настройки стилей из YAML (или подставляем красивые дефолты)
        st = sub_cfg.get('style_settings', {})

        plt.figure(figsize=(10, 5))

        # Название прибора для легенды (например, LZY-1+ или SUCOFLEX)
        short_id = device_config.get('device_short_id', 'Device')

        # 2. Отрисовка основной линии прибора
        plt.plot(freqs_scaled, values,
                 label=short_id,
                 color=st.get('line_color', '#1F497D'),
                 lw=st.get('line_width', 1.5),
                 zorder=3)

        # 3. Отрисовка коридора неопределенности k=2
        if show_unc:
            u_expanded = u_std * 2
            plt.fill_between(freqs_scaled, values - u_expanded, values + u_expanded,
                             color=st.get('uncertainty_color', '#7292C5'),
                             alpha=st.get('uncertainty_alpha', 0.20),
                             lw=st.get('line_width', 1.5)/2,
                             label='Неопределённость',
                             zorder=2)

        # 4. Отрисовка линии лимита/допуска
        if sub_cfg.get('show_limit_line', False):
            limit_val = sub_cfg.get('limit_value_db')
            plt.axhline(y=limit_val,
                        color=st.get('limit_color', '#C00000'),
                        linestyle=st.get('limit_style', '--'),
                        lw=st.get('limit_width', 1.2),
                        label='Лимит',
                        zorder=4)

        # 5. 💡 МЕТРОЛОГИЧЕСКОЕ ЗАТЕМНЕНИЕ НЕРАБОЧИХ ОБЛАСТЕЙ (ПО ВАШЕМУ РЕФЕРЕНСУ)
        sh_color = st.get('shading_color', '#F2F2F2')
        sh_alpha = st.get('shading_alpha', 0.6)

        plt_x_min = plt.xlim()[0]
        plt_x_max = plt.xlim()[1]

        # Левая нерабочая зона (от самого начала до f_min_spec)
        if plt_x_min < f_min_spec:
            plt.axvspan(plt_x_min, f_min_spec, color=sh_color, alpha=sh_alpha, zorder=1)
        # Правая нерабочая зона (от f_max_spec до самого конца файла)
        if plt_x_max > f_max_spec:
            plt.axvspan(f_max_spec, plt_x_max, color=sh_color, alpha=sh_alpha, zorder=1)

        # 6. 💡 ПОИСК И ВЫВОД МАКСИМУМА НЕОПРЕДЕЛЕННОСТИ (СТРЕЛКА-ВЫНОСКА)
        # Ищем максимум только внутри исследуемого (незатемненного) диапазона
        mask = (freqs_scaled >= f_min_spec) & (freqs_scaled <= f_max_spec)
        if np.any(mask):
            u_expanded_zone = (u_std * 2)[mask]
            freqs_zone = freqs_scaled[mask]
            values_zone = values[mask]

            max_idx_in_zone = np.argmax(u_expanded_zone)

            max_f = freqs_zone[max_idx_in_zone]
            max_val = values_zone[max_idx_in_zone]
            max_u = u_expanded_zone[max_idx_in_zone]

            plt.scatter(max_f, max_val, color='black', s=6, zorder=5)

            annotation_text = f"F={max_f:.1f}\nMax={max_u:.2f}"

            plt_y_min = plt.ylim()[0]

            plt.annotate(
                annotation_text,
                xy=(max_f, max_val),
                xytext=(max_f - (freqs_scaled.max() - freqs_scaled.min()) * 0.15, plt_y_min - (plt_y_min - max_val)/2),
                arrowprops=dict(arrowstyle="->", color="black", lw=0.7,
                                connectionstyle="angle,angleA=0,angleB=90,rad=5"),
                bbox=dict(boxstyle="round,pad=0.2,rounding_size=0.15", fc="white", edgecolor="lightgrey", lw=0.7),
                fontsize=9,
                zorder=6
            )

        # Базовые настройки осей и сеток
        plt.xscale(sub_cfg.get('x_scale', 'linear'))
        plt.xlim(plt_x_min, plt_x_max)
        plt.grid(True, which='major', ls="-", alpha=0.5, zorder=0, lw=0.3)
        plt.minorticks_on()
        plt.grid(True, which='minor', ls="-", alpha=0.3, zorder=0, lw=0.2)

        # 💡 ИСПРАВЛЕНИЕ: Заменили bold=True на weight='bold' для Matplotlib
        plt.title(sub_cfg.get('title', 'Measurement Plot'), fontsize=11, weight='bold')
        plt.xlabel(f'Частота, {target_unit}')
        plt.ylabel(f'{param_name}, dB')
        plt.legend(loc='upper right', frameon=True)


        # Сохранение файла...
        freq_range_str = FrequencyConverter.format_frequency_range(freqs_hz.min(), freqs_hz.max())
        safe_filename = Visualizer._build_safe_title(
            device_config.get('device_type', 'Device'),
            device_config.get('device_short_id', 'Unknown'),
            str(device_config.get('serial_number', '')),
            freq_range_str
        )

        plot_path = os.path.join(plots_dir, f"{safe_filename}.png")
        plt.savefig(plot_path, dpi=200, bbox_inches='tight')
        plt.close()
        print(f"[Visualizer] Успешно сформирован кастомизированный график: {safe_filename}.png")
