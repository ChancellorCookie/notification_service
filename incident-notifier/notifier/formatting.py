"""Einheitliche Formatierung der Benachrichtigungstexte.

Unterstuetzt konfigurierbare Templates ueber die config.yaml (Sektion 'templates').
Platzhalter werden als {variable} geschrieben. Ist kein Template konfiguriert,
wird das Built-in-Format verwendet.
"""
from .models import Incident

_EMOJI = {"critical": "\U0001F6A8", "warning": "\u26A0\uFE0F", "info": "\u2139\uFE0F",
          "error": "\U0001F6A8", "alert": "\u26A0\uFE0F", "notice": "\u2139\uFE0F"}
_SEVERITY_LABEL = {"critical": "KRITISCH", "error": "FEHLER", "alert": "ALARM",
                   "warning": "WARNUNG", "info": "INFO", "notice": "HINWEIS"}

# Alle verfuegbaren Platzhalter (werden im Web-UI als Referenz angezeigt)
PLACEHOLDER_HELP = {
    "severity": "Severity (z.B. error, warning, info)",
    "severity_label": "Severity als Label (z.B. FEHLER, WARNUNG)",
    "max_severity": "Hoechste jemals erreichte Severity",
    "max_severity_label": "Max-Severity als Label",
    "title": "Titel des Incidents",
    "source": "Quelle (Context-Pfad, z.B. DeviceSet/S1-1016939/...)",
    "device_name": "Geraetename (aus Context extrahiert, z.B. S1-1016939)",
    "description": "Beschreibungstext",
    "timestamp": "Zeitpunkt der Erstellung (ISO)",
    "status": "Status (NEW, ACKNOWLEDGED, CONFIRMED, ...)",
    "id": "Incident-ID (UUID)",
    "url": "Direktlink zum Incident im Tool",
    "event_id": "Ausloesendes Event",
    "help": "Handlungsempfehlung",
    "comment": "Letzter Operator-Kommentar",
    "acknowledged": "Quittiert? (Ja/Nein)",
    "confirmed": "Bestaetigt? (Ja/Nein)",
    "reported": "Gemeldet? (Ja/Nein)",
    "flap_count": "Flatter-Zaehler (0 = kein Flattern)",
    "flap_warning": "Flattern-Warnung wenn flap_count > 0, sonst leer",
    "strict_audited": "Confirm erforderlich? (Ja/Nein)",
    "active": "Condition aktiv? (Ja/Nein)",
    "high_high_limit": "Kritisch-Hoch-Schwelle",
    "high_limit": "Warnung-Hoch-Schwelle",
    "low_limit": "Warnung-Niedrig-Schwelle",
    "low_low_limit": "Kritisch-Niedrig-Schwelle",
    "threshold_list": "Alle Schwellwerte als Text (kommagetrennt)",
    "flags": "Status-Flags als Text (Quittiert, Bestaetigt, ...)",
}


def _substitute(template: str, inc: Incident) -> str:
    """Ersetzt {variable}-Platzhalter mit Werten aus dem Incident."""
    sev_label = _SEVERITY_LABEL.get(inc.severity, inc.severity.upper())
    max_sev_label = _SEVERITY_LABEL.get(inc.max_severity, inc.max_severity.upper()) if inc.max_severity else ""
    ja_nein = lambda b: "Ja" if b else "Nein"

    flags = []
    if inc.acknowledged:
        flags.append("Quittiert")
    if inc.confirmed:
        flags.append("Bestaetigt")
    if inc.reported:
        flags.append("Gemeldet")
    if inc.strict_audited:
        flags.append("Confirm erforderlich")

    thresholds = []
    if inc.high_high_limit is not None:
        thresholds.append(f"Kritisch-Hoch > {inc.high_high_limit}")
    if inc.high_limit is not None:
        thresholds.append(f"Warnung-Hoch > {inc.high_limit}")
    if inc.low_limit is not None:
        thresholds.append(f"Warnung-Niedrig < {inc.low_limit}")
    if inc.low_low_limit is not None:
        thresholds.append(f"Kritisch-Niedrig < {inc.low_low_limit}")

    vals = {
        "severity": inc.severity,
        "severity_label": sev_label,
        "max_severity": inc.max_severity,
        "max_severity_label": max_sev_label,
        "title": inc.title,
        "source": inc.source,
        "device_name": inc.device_name,
        "description": inc.description,
        "timestamp": inc.timestamp or "-",
        "status": inc.status,
        "id": inc.id,
        "url": inc.url,
        "event_id": inc.event_id,
        "help": inc.help,
        "comment": inc.comment,
        "acknowledged": ja_nein(inc.acknowledged),
        "confirmed": ja_nein(inc.confirmed),
        "reported": ja_nein(inc.reported),
        "flap_count": str(inc.flap_count),
        "flap_warning": f"ALARM FLATTERT {inc.flap_count}x!" if inc.flap_count > 0 else "",
        "strict_audited": ja_nein(inc.strict_audited),
        "active": ja_nein(inc.active),
        "high_high_limit": str(inc.high_high_limit) if inc.high_high_limit is not None else "",
        "high_limit": str(inc.high_limit) if inc.high_limit is not None else "",
        "low_limit": str(inc.low_limit) if inc.low_limit is not None else "",
        "low_low_limit": str(inc.low_low_limit) if inc.low_low_limit is not None else "",
        "threshold_list": ", ".join(thresholds),
        "flags": ", ".join(flags),
    }

    result = template
    for key, val in vals.items():
        result = result.replace("{" + key + "}", str(val))
    return result


# ---------------------------------------------------------------------------
# Built-in Fallback-Templates
# ---------------------------------------------------------------------------

_ALERT_SUBJECT_DEFAULT = "[{severity_label}] [{device_name}] {title}"
_ALERT_BODY_DEFAULT = """Severity:    {severity_label}
Titel:       {title}
Quelle:      {source}
Geraet:      {device_name}
Zeitpunkt:   {timestamp}
Status:      {status}
Incident-ID: {id}
{threshold_list}
{flap_warning}
{flags}

Zum Quittieren oeffnen: {url}

HANDLUNGSEMPFEHLUNG:
{help}

Beschreibung:
{description}"""

_RESOLVED_SUBJECT_DEFAULT = "[ENTWARNUNG] [{device_name}] {title}"
_RESOLVED_BODY_DEFAULT = """Der folgende Vorfall ist nicht mehr offen (quittiert oder geschlossen):

Titel:       {title}
Quelle:      {source}
Geraet:      {device_name}
Incident-ID: {id}"""

_WHATSAPP_TEXT_DEFAULT = "{severity_label} Incident\n{title}\nQuelle: {source}\nGeraet: {device_name}\nStatus: {status}\n{help}\nZeit: {timestamp}\n{url}\nID: {id}"


def _get_template(templates_cfg: dict | None, key: str, default: str) -> str:
    if templates_cfg and templates_cfg.get(key):
        return templates_cfg[key]
    return default


# ---------------------------------------------------------------------------
# Oeffentliche Formatierungs-Funktionen
# ---------------------------------------------------------------------------

def email_subject(inc: Incident, templates_cfg: dict | None = None) -> str:
    tpl = _get_template(templates_cfg, "alert_subject", _ALERT_SUBJECT_DEFAULT)
    return _substitute(tpl, inc)


def email_body(inc: Incident, templates_cfg: dict | None = None) -> str:
    tpl = _get_template(templates_cfg, "alert_body", _ALERT_BODY_DEFAULT)
    return _substitute(tpl, inc)


def resolved_subject(inc: Incident, templates_cfg: dict | None = None) -> str:
    tpl = _get_template(templates_cfg, "resolved_subject", _RESOLVED_SUBJECT_DEFAULT)
    return _substitute(tpl, inc)


def resolved_body(inc: Incident, templates_cfg: dict | None = None) -> str:
    tpl = _get_template(templates_cfg, "resolved_body", _RESOLVED_BODY_DEFAULT)
    return _substitute(tpl, inc)


def whatsapp_text(inc: Incident, templates_cfg: dict | None = None) -> str:
    """Freitext fuer das 24h-Fenster / die Twilio-Sandbox."""
    tpl = _get_template(templates_cfg, "whatsapp_text", _WHATSAPP_TEXT_DEFAULT)
    return _substitute(tpl, inc)


def template_variables(inc: Incident) -> dict:
    """Variablen fuer ein freigegebenes WhatsApp-Template (Positionen 1..n)."""
    sev = _SEVERITY_LABEL.get(inc.severity, inc.severity.upper())
    return {
        "1": sev,
        "2": inc.title,
        "3": inc.device_name or inc.source or "-",
        "4": str(inc.id),
    }
