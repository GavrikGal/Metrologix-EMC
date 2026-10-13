# src/readers/data_providers/provider_factory.py
from .base_provider import BaseDataProvider
from .constant_provider import ConstantDataProvider
from .table_provider import TableDataProvider
from .substitution_provider import SubstitutionDataProvider

class DataProviderFactory:
    """Универсальная фабрика для сборки стратегий получения данных"""
    @staticmethod
    def get_provider(source_type: str, root_dir: str, config: dict) -> BaseDataProvider:
        st = source_type.strip().lower()
        if st == 'constant':
            return ConstantDataProvider(root_dir, config)
        elif st == 'table':
            return TableDataProvider(root_dir, config)
        elif st == 'calculated_substitution':
            return SubstitutionDataProvider(root_dir, config)
        else:
            raise ValueError(f"Неизвестный тип источника данных: {source_type}")
