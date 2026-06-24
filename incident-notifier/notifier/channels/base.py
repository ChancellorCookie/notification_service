"""Basisklasse fuer alle Benachrichtigungskanaele."""
from abc import ABC, abstractmethod
from ..models import Incident


class Channel(ABC):
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    @abstractmethod
    def send(self, inc: Incident, kind: str = "alert") -> None:
        """Verschickt eine Benachrichtigung.

        kind: "alert" (neuer/eskalierter Vorfall) oder "resolved" (Entwarnung).
        Wirft bei Fehlern eine Exception.
        """
        raise NotImplementedError
