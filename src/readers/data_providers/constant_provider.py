# src/readers/data_providers/constant_provider.py
from .base_provider import BaseDataProvider
from src.core.data_structures.parameter import Parameter
from src.core.data_structures.trace import Trace
from src.core.data_structures.uncertainty import Uncertainty


class ConstantDataProvider(BaseDataProvider):
    """Провайдер для создания плоских константных параметров приборов"""

    def get_parameter(self) -> Parameter:
        f_min = float(self.config.get('f_min', 9000.0))
        f_max = float(self.config.get('f_max', 40e9))

        # Читаем единицу измерения из конфига (dB, SWR и т.д., по умолчанию dB)
        val_unit = self.config.get('values_units', 'dB')

        val = float(self.config.get('value', 0.0))
        value_trace = Trace.create_constant(f_min, f_max, val, values_units=val_unit)

        unc_cfg = self.config.get('uncertainty', {})
        uncertainty_trace = None
        if unc_cfg and unc_cfg.get('value') is not None:
            uncertainty_trace = Uncertainty.create_constant(
                f_min=f_min, f_max=f_max,
                value=float(unc_cfg['value']),
                distribution_type=unc_cfg.get('distribution', 'rectangular'),
                k_factor=unc_cfg.get('k_factor', 2.0),
                values_units='dB'  # Погрешности в ЭМС паспортах всегда в дБ
            )

        # 🌟 ИСПРАВЛЕНИЕ: Передаем имя параметра первым аргументом!
        param_name = self.config.get('parameter_system_name', 'Constant_Parameter')
        return Parameter(param_name, value_trace, uncertainty_trace)
