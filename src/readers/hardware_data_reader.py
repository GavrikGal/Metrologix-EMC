# Файл: src/readers/hardware_data_reader.py
import io
import os
import pandas as pd
import numpy as np


class HardwareDataReader:
    """Универсальный менеджер чтения измерительных и калибровочных данных (CSV, TXT, Excel)"""

    @staticmethod
    def read_measurement_data(file_path: str,
                              file_format: str = "text",
                              data_start_marker: str = None,
                              skip_rows: int = 0,
                              delimiter: str = ',',
                              use_columns: list = None,
                              nan_values: list = None) -> pd.DataFrame:
        """
        Единый универсальный метод для чтения любых табличных данных оборудования.

        :param file_path: Абсолютный или относительный путь к файлу
        :param file_format: Формат файла: 'text' (для CSV/TXT) или 'excel' (для .xlsx/.xls)
        :param data_start_marker: Текстовый маркер начала данных (например, 'DATA') для текстовых файлов
        :param skip_rows: Фиксированное число строк для пропуска сверху (для Excel или простых CSV)
        :param delimiter: Разделитель колонок (применяется для формата 'text')
        :param use_columns: Индексы колонок, которые необходимо загрузить
        :param nan_values: Список технических маркеров ошибок, заменяемых на NaN
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"[DataReader] Файл не найден по пути: {file_path}")

        file_format = file_format.strip().lower()

        # --- БЛОК 1: ЧТЕНИЕ ФОРМАТА EXCEL ---
        if file_format == "excel":
            # Читаем Excel-таблицу. Из-за отсутствия шапки в Excel-файлах, header=None
            df = pd.read_excel(file_path, skiprows=skip_rows, header=None)

        # --- БЛОК 2: ЧТЕНИЕ ТЕКСТОВЫХ ФОРМАТОВ (CSV / TXT) ---
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            start_idx = 0
            if data_start_marker:
                for idx, line in enumerate(lines):
                    if data_start_marker in line:
                        start_idx = idx + 1
                        break
                else:
                    raise ValueError(
                        f"[DataReader] Маркер начала данных '{data_start_marker}' не найден в файле: {file_path}")
            else:
                start_idx = skip_rows

            useful_lines = "".join(lines[start_idx:])
            df = pd.read_csv(io.StringIO(useful_lines), sep=delimiter, header=None)

        # --- БЛОК 3: УНИВЕРСАЛЬНАЯ ФИЛЬТРАЦИЯ И ОЧИСТКА ---
        if use_columns is not None:
            df = df[use_columns]

        if nan_values:
            for val in nan_values:
                df.replace(val, np.nan, inplace=True)

        return df
