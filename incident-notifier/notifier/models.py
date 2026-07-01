"""Datenmodell fuer einen Incident, unabhaengig von der konkreten Monitoring-API."""
from dataclasses import dataclass, field


@dataclass
class Incident:
    id: str
    title: str
    severity: str = "info"        # NOTICE | INFO | WARNING | ALERT | ERROR  (LCC API)
    source: str = ""              # Host / Geraet / Komponente
    description: str = ""
    timestamp: str | None = None
    status: str = "open"          # NEW | ACKNOWLEDGED | CONFIRMED | REPORTED | CLOSED | RESOLVED
    url: str = ""                 # Direktlink zum Incident im Monitoring-Tool
    raw: dict = field(default_factory=dict)

    # ----------------------------------------------------------------
    # Zusaetzliche Felder aus der LCC Incidents API (v2)
    # ----------------------------------------------------------------
    max_severity: str = ""         # hoechste jemals erreichte Severity (bleibt bei Peak)
    help: str = ""                # Hinweistext, wie der Vorfall zu beheben ist
    comment: str = ""             # letzter Operator-Kommentar (Ack/Confirm/Reset)
    acknowledged: bool = False    # AuditConditionAcknowledge erfasst?
    confirmed: bool = False       # AuditConditionConfirm erfasst?
    reported: bool = False        # AuditConditionReportedEventType erfasst? (Eskalation)
    flap_count: int = 0           # Anzahl ConditionBranches (Alarm-Flattern), 0 = kein Flattern
    strict_audited: bool = False  # braucht explicit Confirm zum Schliessen?
    active: bool = True           # Ist die zugrundeliegende Condition noch aktiv?
    event_id: str = ""            # ausloesendes Event

    # Alarm-Schwellwerte (LimitAlarm)
    high_high_limit: float | None = None  # kritisch-hoch
    high_limit: float | None = None       # warnung-hoch
    low_limit: float | None = None        # warnung-niedrig
    low_low_limit: float | None = None    # kritisch-niedrig

    # Raum-Infos (angereichert ueber GET /rooms/ + Monitoring-Pfad-Matching)
    room_name: str = ""
    room_number: str = ""
    room_contact_name: str = ""
    room_contact_email: str = ""
    room_contact_details: str = ""

    @property
    def device_name(self) -> str:
        """Extrahiert den Geraetenamen aus dem context-Pfad.

        'DeviceSet/S1-1016939/FunctionalUnitSet/Fumehood/FunctionSet/Airflow'
        -> 'S1-1016939'
        """
        import re
        m = re.search(r"DeviceSet/([^/]+)", self.source)
        return m.group(1) if m else self.source
