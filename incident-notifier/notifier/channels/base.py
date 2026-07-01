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
        raise NotImplementedError

    def send_digest(self, incidents: list[Incident]) -> None:
        return self.send(incidents[0], kind="digest")
