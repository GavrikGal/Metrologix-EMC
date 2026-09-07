import io
import pandas as pd
import numpy as np


class UniversalCSVReader:
    """Универсальный настраиваемый ридер для любых текстовых и CSV файлов оборудования"""

    @staticmethod
    def read_csv_data(file_path: str,
                      data_start_marker: str = None,
                      skip_rows: int = 0,
                      delimiter: str = ',',
                      use_columns: list = None,
                      nan_values: list = None) -> pd.DataFrame:
        """
        Универсальный метод чтения табличных данных.

        :param file_path: Путь к файлу
        :param data_start_marker: Текстовый маркер, после которого начинаются данные (например, 'DATA')
        :param skip_rows: Фиксированное количество строк для пропуска сверху (если маркер не задан)
        :param delimiter: Разделитель колонок (запятая, точка с запятой, пробел)
        :param use_columns: Список индексов колонок, которые нужно оставить (например, [0, 1, 2, 3])
        :param nan_values: Список специфических значений, которые нужно заменить на NaN (например, [-893.01])
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 1. Определяем, откуда начинаются данные
        start_idx = 0
        if data_start_marker:
            for idx, line in enumerate(lines):
                if line.strip() == data_start_marker:
                    start_idx = idx + 1
                    break
            else:
                raise ValueError(f"Маркер начала данных '{data_start_marker}' не найден в файле: {file_path}")
        else:
            start_idx = skip_rows

        # 2. Собираем полезные строки в виртуальный файл в памяти
        useful_data = "".join(lines[start_idx:])

        # 3. Читаем с помощью pandas
        df = pd.read_csv(io.StringIO(useful_data), sep=delimiter, header=None)

        # 4. Фильтруем колонки, если это задано
        if use_columns is not None:
            df = df[use_columns]

        # 5. Заменяем технический "мусор" приборов на честный NaN
        if nan_values:
            for val in nan_values:
                df.replace(val, np.nan, inplace=True)

        return df
