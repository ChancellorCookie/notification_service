"""Fragt die Monitoring-REST-API ab und liefert eine Liste offener Incidents.

Die Zuordnung der JSON-Felder zum Incident-Modell ist komplett ueber die
Konfiguration steuerbar (response.fields), damit der Dienst an die konkrete
API der Monitoring-Software angepasst werden kann, ohne Code zu aendern.

Der Direktlink zum Incident kommt entweder aus einem API-Feld (response.fields.url)
oder wird aus poll.incident_url_template gebaut, z.B.
"https://monitoring.local/incidents/{id}".

Auth-Typen:
  - none:     keine Authentifizierung
  - bearer:   statisches Token (Authorization: Bearer <token>)
  - basic:    HTTP Basic Auth
  - oauth2:   OAuth2 Client Credentials Flow (machine-to-machine).
              Holt automatisch ein Token vom konfigurierten token_url-Endpunkt
              und cached es bis zum Ablauf.

Unterstuetzt:
  - query_params: zusaetzliche URL-Query-Parameter (z.B. lifecycle=open)
  - Paginierung: automatisches Abholen aller Seiten (response.pagination konfigurierbar)
  - report_incident: POST /lads/alarms/{incidentId}/report als Dummy (loggt nur)
"""
import logging
import time
import requests

from .config import get_by_path
from .models import Incident

log = logging.getLogger("notifier.poller")


def _token_key(client_id):
    return f"_oauth2_token_{client_id}"


class Poller:
    def __init__(self, config: dict):
        self.c = config
        self.url_template = config.get("incident_url_template", "")
        self.query_params = config.get("query_params", {}) or {}
        self.pg = config.get("pagination", {}) or {}
        self.report_cfg = config.get("report_incident", {}) or {}
        self.session = requests.Session()
        self._token_cache = {}  # client_id -> {"token": str, "expires_at": float}

        auth = config.get("auth", {}) or {}
        atype = auth.get("type", "none")
        if atype == "bearer":
            self.session.headers["Authorization"] = f"Bearer {auth.get('token', '')}"
        elif atype == "basic":
            self.session.auth = (auth.get("username", ""), auth.get("password", ""))
        elif atype == "oauth2":
            # Token wird lazy beim ersten Request geholt (in _ensure_token)
            pass

    def _oauth2_config(self):
        return self.c.get("auth", {}) or {}

    def _ensure_token(self):
        """Holt ein OAuth2-Token per Client-Credentials-Flow, falls noetig."""
        oa = self._oauth2_config()
        if oa.get("type") != "oauth2":
            return

        cid = oa.get("client_id", "")
        ckey = _token_key(cid)
        cached = self._token_cache.get(ckey)

        if cached and cached["expires_at"] > time.time() + 10:
            self.session.headers["Authorization"] = f"Bearer {cached['token']}"
            return

        token_url = oa.get("token_url", "")
        if not token_url:
            log.error("oauth2 konfiguriert, aber token_url fehlt")
            return

        log.info("Hole OAuth2-Token von %s (client_id=%s)", token_url, cid)
        payload = {
            "grant_type": "client_credentials",
            "client_id": cid,
            "client_secret": oa.get("client_secret", ""),
        }
        scope = oa.get("scope", "")
        if scope:
            payload["scope"] = scope
        audience = oa.get("audience", "")
        if audience:
            payload["audience"] = audience

        resp = requests.post(
            token_url,
            data=payload,
            timeout=oa.get("timeout_seconds", 10),
            verify=self.c.get("verify_tls", True),
        )
        resp.raise_for_status()
        data = resp.json()

        token = data.get("access_token", "")
        expires_in = int(data.get("expires_in", 3600))
        if not token:
            raise RuntimeError(f"Token-Endpoint lieferte kein access_token: {data}")

        self._token_cache[ckey] = {
            "token": token,
            "expires_at": time.time() + expires_in,
        }
        self.session.headers["Authorization"] = f"Bearer {token}"
        log.info("OAuth2-Token erhalten, gueltig fuer %ds", expires_in)

    def report_incident(self, incident_id: str, comment: str = ""):
        """Markiert einen Incident in der Monitoring-Software als 'reported'
        (Eskalations-Schritt dokumentiert).

        Aktuell DUMMY-Implementierung: loggt nur, sendet kein echtes POST.
        Sobald die API erreichbar ist, wird hier das POST abgesetzt.
        """
        enabled = bool(self.report_cfg.get("enabled", False))
        if not enabled:
            log.debug("report_incident deaktiviert, ueberspringe %s", incident_id)
            return

        url_tpl = self.report_cfg.get(
            "url_template", "{base_url}/lads/alarms/{incident_id}/report"
        )
        base = self.c.get("url", "").rstrip("/")
        url = url_tpl.format(base_url=base, incident_id=incident_id)

        payload = {}
        if comment:
            payload["comment"] = comment

        log.info(
            "[DUMMY] report_incident wuerde POST an %s senden (payload=%s)",
            url, payload,
        )

    def fetch(self):
        self._ensure_token()
        c = self.c
        verify = c.get("verify_tls", True)
        rcfg = c.get("response", {})
        fields = rcfg.get("fields", {})
        allowed = set(c.get("severities", [])) or None

        all_items = []
        offset = 0
        limit = self.pg.get("page_size", 0)

        while True:
            params = dict(self.query_params)
            if limit > 0:
                params[self.pg.get("offset_param", "offset")] = offset
                params[self.pg.get("limit_param", "limit")] = limit

            resp = self.session.request(
                c.get("method", "GET"),
                c["url"],
                params=params or None,
                timeout=c.get("timeout_seconds", 10),
                verify=verify,
            )
            resp.raise_for_status()
            data = resp.json()

            items = get_by_path(data, rcfg.get("items_path", "")) or []
            if not isinstance(items, list):
                log.warning("items_path lieferte kein Array, ignoriere Antwort")
                return []

            for item in items:
                inc = self._map(item, fields)
                if allowed and inc.severity not in allowed:
                    continue
                all_items.append(inc)

            if limit <= 0:
                break

            total_path = self.pg.get("total_path", "")
            total = get_by_path(data, total_path) if total_path else 0
            if not total:
                total = len(items)
            offset += len(items)
            if offset >= total:
                break

        return all_items

    def _map(self, item: dict, fields: dict) -> Incident:
        def f(name, default=""):
            path = fields.get(name)
            if not path:
                return default
            val = get_by_path(item, path)
            return default if val is None else val

        def fbool(name, default=False):
            path = fields.get(name)
            if not path:
                return default
            val = get_by_path(item, path)
            return bool(val) if val is not None else default

        def ffloat(name, default=None):
            path = fields.get(name)
            if not path:
                return default
            val = get_by_path(item, path)
            if val is None:
                return default
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

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

            max_severity=str(f("max_severity", "")).lower(),
            help=str(f("help", "")),
            comment=str(f("comment", "")),
            acknowledged=fbool("acknowledged"),
            confirmed=fbool("confirmed"),
            reported=fbool("reported"),
            flap_count=int(f("flap_count", 0) or 0),
            strict_audited=fbool("strict_audited"),
            active=fbool("active", True),
            event_id=str(f("event_id", "")),
            updated_at=f("updated_at", None),
            closed_at=f("closed_at", None),
            high_high_limit=ffloat("high_high_limit"),
            high_limit=ffloat("high_limit"),
            low_limit=ffloat("low_limit"),
            low_low_limit=ffloat("low_low_limit"),
        )
        if not inc.url and self.url_template:
            inc.url = self.url_template.format(id=inc.id)
        return inc
