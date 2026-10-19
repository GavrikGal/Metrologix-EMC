# src/readers/data_providers/table_provider.py
import os
import numpy as np
import logging
from .base_provider import BaseDataProvider
from src.readers.hardware_data_reader import HardwareDataReader
from src.core.data_structures.parameter import Parameter
from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty

logger = logging.getLogger("Metrologix")


class TableDataProvider(BaseDataProvider):
    """Провайдер для чтения оцифрованных калибровочных таблиц из Excel/Text"""

    def get_parameter(self) -> Parameter:
        r_set = self.config.get('reader_settings', {})
        cols = self.config.get('columns_mapping', {'frequency': 0, 'value': 1})
        val_unit = self.config.get('values_units', 'dB')

        full_path = os.path.join(self.root_dir, self.config['file_path'])
        df = HardwareDataReader.read_measurement_data(
            file_path=full_path, file_format=r_set.get('file_format', 'excel'),
            skip_rows=r_set.get('skip_rows', 1), delimiter=r_set.get('delimiter', ',')
        )

        from src.core.math_models import FrequencyConverter
        src_unit = r_set.get('file_frequency_unit', 'MHz')
        ratio = FrequencyConverter.get_ratio(from_unit=src_unit, to_unit='Hz')

        freqs_hz = df[cols['frequency']].values.astype(float) * ratio
        values = df[cols['value']].values.astype(float)

        value_trace = Trace(freqs_hz, values, values_units=val_unit)

        uncertainty_trace = None
        if 'uncertainty' in cols and cols['uncertainty'] in df.columns:
            unc_values = df[cols['uncertainty']].values.astype(float)
            unc_cfg = self.config.get('uncertainty', {})
            uncertainty_trace = Uncertainty(
                frequencies=freqs_hz, values=unc_values, values_units='dB',
                distribution_type=unc_cfg.get('distribution', 'normal'),
                k_factor=unc_cfg.get('k_factor', 2.0)
            )

        # 🌟 ИСПРАВЛЕНИЕ: Передаем имя параметра первым аргументом!
        param_name = self.config.get('parameter_system_name', 'Table_Parameter')
        return Parameter(param_name, value_trace, uncertainty_trace)
