"""Basisklasse fuer alle Benachrichtigungskanaele."""
from abc import ABC, abstractmethod
from ..models import Incident


class Channel(ABC):
    def __init__(self, name: str, config: dict, templates_cfg: dict | None = None):
        self.name = name
        self.config = config
        self.templates_cfg = templates_cfg or {}

    @abstractmethod
    def send(self, inc: Incident, kind: str = "alert") -> None:
        """Verschickt eine Benachrichtigung.

        kind: "alert" (neuer/eskalierter Vorfall) oder "resolved" (Entwarnung).
        Wirft bei Fehlern eine Exception.
        """
        raise NotImplementedError
