# src/readers/data_providers/table_provider.py
import os
import numpy as np
from .base_provider import BaseDataProvider
from src.readers.hardware_data_reader import HardwareDataReader
from src.core.math_models import FrequencyConverter
from src.core.data_structures.parameter import Parameter
from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty

class TableDataProvider(BaseDataProvider):
    def get_parameter(self) -> Parameter:
        file_path = os.path.join(self.root_dir, self.config.get('file_path'))
        r_set = self.config.get('reader_settings', {})
        mapping = self.config.get('columns_mapping', {'frequency': 0, 'value': 1, 'uncertainty': 2})

        # Чтение низкоуровневой таблицы
        df = HardwareDataReader.read_measurement_data(
            file_path=file_path, file_format=r_set.get('file_format', 'text'),
            skip_rows=r_set.get('skip_rows', 0), delimiter=r_set.get('delimiter', ',')
        )

        raw_freqs = df[mapping['frequency']].values.astype(float)
        values = df[mapping['value']].values.astype(float)

        # Конвертация оси частот в системные Герцы
        src_unit = r_set.get('file_frequency_unit', 'Hz')
        ratio = FrequencyConverter.get_ratio(from_unit=src_unit, to_unit='Hz')
        freqs_hz = raw_freqs * ratio

        # Инициализация метрологических сущностей с сырыми данными
        value_trace = Trace(freqs_hz, values)

        unc_cfg = self.config.get('uncertainty', {})
        uncertainty_trace = None
        if unc_cfg:
            if unc_cfg.get('type') == 'constant':
                unc_values = np.full_like(freqs_hz, unc_cfg.get('value', 0.0))
            else:
                unc_values = df[mapping['uncertainty']].values.astype(float)

            uncertainty_trace = Uncertainty(
                frequencies=freqs_hz,
                values=unc_values,
                distribution_type=unc_cfg.get('distribution', 'normal'),
                k_factor=unc_cfg.get('k_factor', 2.0)  # 🌟 ИСПРАВЛЕНО
            )

        return Parameter(value_trace, uncertainty_trace)
