# src/readers/data_providers/base_provider.py
from abc import ABC, abstractmethod
from src.core.data_structures.parameter import Parameter

class BaseDataProvider(ABC):
    def __init__(self, root_dir: str, config: dict) -> None:
        self.root_dir = root_dir
        self.config = config

    @abstractmethod
    def get_parameter(self) -> Parameter:
        """Выполняет загрузку, фильтрацию и математический синтез метрологического параметра"""
        pass
