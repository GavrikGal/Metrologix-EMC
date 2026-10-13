# src/reports/base_renderer.py
from abc import ABC, abstractmethod


class BaseRenderer(ABC):
    """
    Абстрактный базовый класс (контракт) для всех компонентов отчетности.
    Гарантирует единую точку входа 'render' для графиков, таблиц и поправок.
    """

    @abstractmethod
    def render(self, *args, **kwargs) -> None:
        """Метод реализации рендеринга конкретного типа документа"""
        pass
