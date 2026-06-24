"""Fragt die Monitoring-REST-API ab und liefert eine Liste offener Incidents.

Die Zuordnung der JSON-Felder zum Incident-Modell ist komplett ueber die
Konfiguration steuerbar (response.fields), damit der Dienst an die konkrete
API der Monitoring-Software angepasst werden kann, ohne Code zu aendern.

Der Direktlink zum Incident kommt entweder aus einem API-Feld (response.fields.url)
oder wird aus poll.incident_url_template gebaut, z.B.
"https://monitoring.local/incidents/{id}".
"""
import logging
import requests

from .config import get_by_path
from .models import Incident

log = logging.getLogger("notifier.poller")


class Poller:
    def __init__(self, config: dict):
        self.c = config
        self.url_template = config.get("incident_url_template", "")
        self.session = requests.Session()
        auth = config.get("auth", {}) or {}
        atype = auth.get("type", "none")
        if atype == "bearer":
            self.session.headers["Authorization"] = f"Bearer {auth.get('token', '')}"
        elif atype == "basic":
            self.session.auth = (auth.get("username", ""), auth.get("password", ""))

    def fetch(self):
        c = self.c
        verify = c.get("verify_tls", True)  # bool oder Pfad zur CA-Datei
        resp = self.session.request(
            c.get("method", "GET"),
            c["url"],
            timeout=c.get("timeout_seconds", 10),
            verify=verify,
        )
        resp.raise_for_status()
        data = resp.json()

        rcfg = c.get("response", {})
        items = get_by_path(data, rcfg.get("items_path", "")) or []
        if not isinstance(items, list):
            log.warning("items_path lieferte kein Array, ignoriere Antwort")
            return []

        fields = rcfg.get("fields", {})
        allowed = set(c.get("severities", [])) or None
        out = []
        for item in items:
            inc = self._map(item, fields)
            if allowed and inc.severity not in allowed:
                continue
            out.append(inc)
        return out

    def _map(self, item: dict, fields: dict) -> Incident:
        def f(name, default=""):
            path = fields.get(name)
            if not path:
                return default
            val = get_by_path(item, path)
            return default if val is None else val

        inc = Incident(
            id=str(f("id")),
            title=str(f("title", "Unbenannter Incident")),
            severity=str(f("severity", "info")).lower(),
            source=str(f("source", "")),
            description=str(f("description", "")),
            timestamp=f("timestamp", None),
            status=str(f("status", "open")),
            url=str(f("url", "")),
            raw=item,
        )
        if not inc.url and self.url_template:
            inc.url = self.url_template.format(id=inc.id)
        return inc
