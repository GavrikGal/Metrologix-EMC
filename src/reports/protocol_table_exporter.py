# Файл: src/reports/protocol_table_exporter.py
import os
import pandas as pd
import numpy as np
from src.core.math_models import FrequencyConverter


class ProtocolTableExporter:
    """Универсальный модуль формирования табличных материалов для метрологического протокола"""

    @staticmethod
    def export_raw_slice(output_dir: str, filename: str, raw_slice_data: dict,
                         target_unit: str, param_name: str):
        """Формирует расширенную таблицу протокола с динамическими именами параметров"""
        tables_dir = os.path.join(output_dir, "protocol_tables")
        os.makedirs(tables_dir, exist_ok=True)

        freqs_hz = raw_slice_data['freq_hz']
        ratio = FrequencyConverter.get_ratio(from_unit="Hz", to_unit=target_unit)
        scaled_frequencies = freqs_hz * ratio

        # Базовая структура таблицы
        protocol_dict = {
            f'Frequency [{target_unit}]': np.round(scaled_frequencies, 6)
        }

        # 1. Добавляем сырые трассы Опорного сигнала (Baseline / Система 1)
        sys1_matrix = raw_slice_data['sys1_traces']
        for t_idx in range(sys1_matrix.shape[1]):
            protocol_dict[f'Baseline_Trace_{t_idx + 1} [dBuV]'] = np.round(sys1_matrix[:, t_idx], 3)

        # 2. Добавляем промежуточный расчет: Среднее значение Опоры
        protocol_dict['Baseline_Mean [dBuV]'] = np.round(raw_slice_data['sys1_mean_db'], 3)

        # 3. Добавляем сырые трассы Измеряемого тракта (Target / Система 2)
        sys2_matrix = raw_slice_data['sys2_traces']
        for t_idx in range(sys2_matrix.shape[1]):
            protocol_dict[f'Target_Trace_{t_idx + 1} [dBuV]'] = np.round(sys2_matrix[:, t_idx], 3)

        # 4. Добавляем промежуточный расчет: Среднее значение Тракта
        protocol_dict['Target_Mean [dBuV]'] = np.round(raw_slice_data['sys2_mean_db'], 3)

        # 💡 ИСПРАВЛЕНИЕ: Имя столбца теперь формируется ДИНАМИЧЕСКИ на основе param_name!
        protocol_dict[f'Calculated {param_name} [dB]'] = np.round(raw_slice_data['values_db'], 3)

        # Финальные метрологические результаты неопределенностей
        protocol_dict['Uncertainty u(xi) [dB] (k=1)'] = np.round(raw_slice_data['raw_uncertainty_db'], 4)
        protocol_dict['Expanded Uncertainty [dB] (k=2)'] = np.round(raw_slice_data['raw_uncertainty_db'] * 2, 3)

        # Сохраняем в CSV
        df_protocol = pd.DataFrame(protocol_dict)
        table_path = os.path.join(tables_dir, f"{filename}.csv")
        df_protocol.to_csv(table_path, index=False, sep=';', encoding='utf-8-sig')
        print(f"[Protocol Exporter] Создана таблица параметра '{param_name}': {filename}.csv")
