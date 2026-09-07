import os
import numpy as np
import matplotlib.pyplot as plt


class Visualizer:
    """Универсальный графический движок системы Metrologix EMC"""

    @staticmethod
    def draw_subplot(task_output_dir: str, device_name: str,
                     freqs: np.ndarray, values: np.ndarray, u_std: np.ndarray,
                     sub_cfg: dict, show_unc: bool = True):
        """
        Отрисовывает один конкретный график (поддиапазон) для параметра прибора
        и сохраняет его в папку output задачи.
        """
        plots_dir = os.path.join(task_output_dir, "plots")
        os.makedirs(plots_dir, exist_ok=True)

        plt.figure(figsize=(10, 5))
        freq_mhz = freqs / 1e6  # Переводим Гц в МГц для наглядности шкалы

        # 1. Линия средних значений (например, затухание S21)
        plt.plot(freq_mhz, values, label=f'{device_name} Mean', color='darkblue', lw=1.5)

        # 2. Теневой коридор расширенной неопределенности k=2 (95%)
        if show_unc:
            u_expanded = u_std * 2
            plt.fill_between(freq_mhz, values - u_expanded, values + u_expanded,
                             color='royalblue', alpha=0.15, label='Expanded Uncertainty (k=2, 95%)')

        # 3. Линия лимита/допуска (если включена пользователем в задаче)
        if sub_cfg.get('show_limit_line', False):
            limit_val = sub_cfg.get('limit_value_db')
            plt.axhline(y=limit_val, color='red', linestyle='--',
                        label=f"Limit ({limit_val} dB)")

        # Настройки отображения
        plt.xscale(sub_cfg.get('x_scale', 'linear'))
        plt.grid(True, which="both", ls=":", alpha=0.5)
        plt.title(sub_cfg.get('title', 'Measurement Data'))
        plt.xlabel('Frequency (MHz)')
        plt.ylabel('Value (dB)')
        plt.legend(loc='best')

        # Защита имени файла от спецсимволов
        safe_title = sub_cfg.get('title').replace(" ", "_").replace("-", "").replace("(", "").replace(")", "")
        plot_path = os.path.join(plots_dir, f"{safe_title}.png")

        plt.savefig(plot_path, dpi=200, bbox_inches='tight')
        plt.close()
        print(f"[Visualizer] График успешно сформирован и сохранен: {plot_path}")
