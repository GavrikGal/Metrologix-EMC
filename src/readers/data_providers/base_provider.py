# src/readers/data_providers/base_provider.py
from abc import ABC, abstractmethod
from src.core.data_structures.parameter import Parameter

class BaseDataProvider(ABC):
    def __init__(self, root_dir: str, config: dict) -> None:
        self.root_dir = root_dir
        self.config = config

    @abstractmethod
    def load_parameter(self) -> Parameter:
        """Возвращает Parameter со стабильными ссылками на сырые Trace и Uncertainty"""
        pass
