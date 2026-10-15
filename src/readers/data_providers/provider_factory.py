# src/readers/data_providers/provider_factory.py
from .base_provider import BaseDataProvider
from .calculated_mismatch_provider import CalculatedMismatchProvider
from .constant_provider import ConstantDataProvider
from .noise_floor_provider import NoiseFloorDataProvider
from .table_provider import TableDataProvider
from .calculated_trace_difference_provider import CalculatedTraceDifferenceProvider

class DataProviderFactory:
    """Универсальная фабрика для сборки стратегий получения данных"""
    @staticmethod
    def get_provider(source_type: str, root_dir: str, config: dict) -> BaseDataProvider:
        st = source_type.strip().lower()
        if st == 'constant':
            return ConstantDataProvider(root_dir, config)
        elif st == 'table':
            return TableDataProvider(root_dir, config)
        elif st == 'calculated_trace_difference':
            return CalculatedTraceDifferenceProvider(root_dir, config)
        elif st == 'calculated_noise_floor':
            return NoiseFloorDataProvider(root_dir, config)
        elif st == 'calculated_mismatch':
            return CalculatedMismatchProvider(root_dir, config)
        else:
            raise ValueError(f"Неизвестный тип источника данных: {source_type}")
