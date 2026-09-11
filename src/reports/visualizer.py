# Файл: src/reports/visualizer.py
import os
import matplotlib.pyplot as plt
import numpy as np


class Visualizer:
    """Графический движок: отвечает СТРОГО за отрисовку графиков (Single Responsibility)"""

    @staticmethod
    def draw_subplot(output_dir: str, device_name: str, filename: str,
                     freqs_hz: np.ndarray, values: np.ndarray, u_std: np.ndarray,
                     sub_cfg: dict, show_unc: bool = True):
        plots_dir = os.path.join(output_dir, "plots")
        os.makedirs(plots_dir, exist_ok=True)

        plt.figure(figsize=(10, 5))
        freq_mhz = freqs_hz / 1e6  # График всегда традиционно строим в МГц для наглядности сетки

        plt.plot(freq_mhz, values, label=f'{device_name} Mean', color='darkblue', lw=1.5)

        if show_unc:
            u_expanded = u_std * 2
            plt.fill_between(freq_mhz, values - u_expanded, values + u_expanded,
                             color='royalblue', alpha=0.15, label='Expanded Uncertainty (k=2, 95%)')

        if sub_cfg.get('show_limit_line', False):
            limit_val = sub_cfg.get('limit_value_db')
            plt.axhline(y=limit_val, color='red', linestyle='--', label=f"Limit ({limit_val} dB)")

        plt.xscale(sub_cfg.get('x_scale', 'linear'))
        plt.grid(True, which="both", ls=":", alpha=0.5)
        plt.title(sub_cfg.get('title', 'Measurement Plot'), fontsize=10)
        plt.xlabel('Frequency (MHz)')
        plt.ylabel('Value (dB)')
        plt.legend(loc='best')

        plot_path = os.path.join(plots_dir, f"{filename}.png")
        plt.savefig(plot_path, dpi=200, bbox_inches='tight')
        plt.close()
