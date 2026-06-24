"""Datenmodell fuer einen Incident, unabhaengig von der konkreten Monitoring-API."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Incident:
    id: str
    title: str
    severity: str = "info"        # z.B. critical | warning | info
    source: str = ""              # Host / Geraet / Komponente
    description: str = ""
    timestamp: Optional[str] = None
    status: str = "open"          # open | resolved (falls die API das liefert)
    url: str = ""                 # Direktlink zum Incident im Monitoring-Tool
    raw: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Stabiler Schluessel fuer die Deduplizierung."""
        return str(self.id)
