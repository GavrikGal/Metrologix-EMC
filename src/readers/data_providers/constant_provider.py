# src/readers/data_providers/constant_provider.py
import numpy as np
from .base_provider import BaseDataProvider
from src.core.data_structures.parameter import Parameter
from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty

class ConstantDataProvider(BaseDataProvider):
    def load_parameter(self) -> Parameter:
        # Для константы берем границы диапазона прибора
        f_min = float(self.config.get('f_min', 9000.0))
        f_max = float(self.config.get('f_max', 40e9))

        # Создаем константный Trace (хранит всего 2 крайние точки диапазона)
        val = float(self.config.get('value', 0.0))
        value_trace = Trace.create_constant(f_min, f_max, val)

        # Создаем константную Uncertainty
        unc_cfg = self.config.get('uncertainty', {})
        uncertainty_trace = None
        if unc_cfg and unc_cfg.get('value') is not None:
            uncertainty_trace = Uncertainty.create_constant(
                f_min=f_min, f_max=f_max,
                value=float(unc_cfg['value']),
                distribution_type=unc_cfg.get('distribution', 'rectangular'),
                k_factor=unc_cfg.get('k_factor', 2.0)  # Скорректировано под k_factor
            )

        return Parameter(value_trace, uncertainty_trace)
