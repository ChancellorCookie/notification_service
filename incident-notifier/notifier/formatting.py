"""Einheitliche Formatierung der Benachrichtigungstexte.

Unterstuetzt konfigurierbare Templates ueber die config.yaml (Sektion 'templates').
Platzhalter werden als {variable} geschrieben. Ist kein Template konfiguriert,
wird das Built-in-Format verwendet.
"""
from .models import Incident

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
    "room_name": "Raumname (z.B. Entwicklungslabor)",
    "room_number": "Raumnummer (z.B. A-101)",
    "room_contact_name": "Ansprechpartner (z.B. Moriz Walter)",
    "room_contact_email": "E-Mail des Ansprechpartners",
    "room_contact_details": "Durchwahl/Details (z.B. T.345)",
    "severity_bg": "(HTML) Hintergrundfarbe passend zur Severity",
    "severity_fg": "(HTML) Textfarbe passend zur Severity",
    "t_limits": "(HTML) Schwellwerte als Tabellenzeilen",
    "t_flags": "(HTML) Status-Flags + Flattern-Warnung als Tabellenzeile",
    "t_help": "(HTML) Handlungsempfehlung als Tabellenzeile",
}


# ---------------------------------------------------------------------------
# Built-in Fallback-Templates
# ---------------------------------------------------------------------------

_ALERT_SUBJECT_DEFAULT = "[{severity_label}] [{room_name}] {title}"
_ALERT_BODY_DEFAULT = """Severity:    {severity_label}
Titel:       {title}
Raum:        {room_name} ({room_number})
Kontakt:     {room_contact_name} ({room_contact_email}, {room_contact_details})
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

_RESOLVED_SUBJECT_DEFAULT = "[ENTWARNUNG] [{room_name}] {title}"
_RESOLVED_BODY_DEFAULT = """Der folgende Vorfall ist nicht mehr offen (quittiert oder geschlossen):

Titel:       {title}
Raum:        {room_name} ({room_number})
Quelle:      {source}
Geraet:      {device_name}
Incident-ID: {id}"""

_WHATSAPP_TEXT_DEFAULT = "{severity_label} Incident\n{title}\nQuelle: {source}\nGeraet: {device_name}\nStatus: {status}\n{help}\nZeit: {timestamp}\n{url}\nID: {id}"

_SEV_COLORS = {
    "error":   ("#dc3545", "#fff"),
    "critical": ("#dc3545", "#fff"),
    "alert":   ("#fd7e14", "#fff"),
    "warning": ("#ffc107", "#212529"),
    "notice":  ("#17a2b8", "#fff"),
    "info":    ("#17a2b8", "#fff"),
}

_ALERT_BODY_HTML_DEFAULT = """\
<html><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;margin:0;padding:0">
<table style="width:100%%;max-width:600px;border-collapse:collapse" cellpadding="0" cellspacing="0">
<tr><td style="background:{severity_bg};color:{severity_fg};padding:16px 20px;font-size:18px;font-weight:bold">
{severity_label} &ndash; {title}
</td></tr>
<tr><td style="padding:16px 20px;border:1px solid #e0e0e0;border-top:none">
<table style="width:100%%;border-collapse:collapse" cellpadding="6" cellspacing="0">
<tr><td style="color:#666;width:140px">Raum</td><td>{room_name} ({room_number})</td></tr>
<tr><td style="color:#666">Kontakt</td><td>{room_contact_name} &lt;{room_contact_email}&gt; {room_contact_details}</td></tr>
<tr><td style="color:#666">Gerät</td><td>{device_name}</td></tr>
<tr><td style="color:#666">Quelle</td><td style="font-size:13px">{source}</td></tr>
<tr><td style="color:#666">Zeitpunkt</td><td>{timestamp}</td></tr>
<tr><td style="color:#666">Status</td><td>{status}</td></tr>
<tr><td style="color:#666">ID</td><td style="font-size:13px">{id}</td></tr>
{t_limits}
{t_flags}
</table>
</td></tr>
{t_help}
<tr><td style="padding:16px 20px;text-align:center">
<a href="{url}" style="display:inline-block;background:#0066cc;color:#fff;padding:10px 24px;text-decoration:none;border-radius:4px;font-weight:bold">Im LCC öffnen</a>
</td></tr>
</table>
</body></html>"""

_RESOLVED_BODY_HTML_DEFAULT = """\
<html><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;margin:0;padding:0">
<table style="width:100%%;max-width:600px;border-collapse:collapse" cellpadding="0" cellspacing="0">
<tr><td style="background:#28a745;color:#fff;padding:16px 20px;font-size:18px;font-weight:bold">
ENTWARNUNG &ndash; {title}
</td></tr>
<tr><td style="padding:16px 20px;border:1px solid #e0e0e0;border-top:none">
<p>Der folgende Vorfall ist nicht mehr offen (quittiert oder geschlossen):</p>
<table style="width:100%%;border-collapse:collapse" cellpadding="6" cellspacing="0">
<tr><td style="color:#666;width:140px">Raum</td><td>{room_name} ({room_number})</td></tr>
<tr><td style="color:#666">Gerät</td><td>{device_name}</td></tr>
<tr><td style="color:#666">Quelle</td><td style="font-size:13px">{source}</td></tr>
<tr><td style="color:#666">ID</td><td style="font-size:13px">{id}</td></tr>
</table>
</td></tr>
</table>
</body></html>"""


def _get_template(templates_cfg: dict | None, key: str, default: str) -> str:
    if templates_cfg and templates_cfg.get(key):
        return templates_cfg[key]
    return default


# ---------------------------------------------------------------------------
# Oeffentliche Formatierungs-Funktionen
# ---------------------------------------------------------------------------

def _substitute_html(template: str, inc: Incident) -> str:
    sev_label = _SEVERITY_LABEL.get(inc.severity, inc.severity.upper())
    sev_color = _SEV_COLORS.get(inc.severity, ("#6c757d", "#fff"))

    limits = []
    if inc.high_high_limit is not None:
        limits.append(f"<tr><td style='color:#666'>Kritisch-Hoch</td><td style='color:#dc3545;font-weight:bold'>&gt; {inc.high_high_limit}</td></tr>")
    if inc.high_limit is not None:
        limits.append(f"<tr><td style='color:#666'>Warnung-Hoch</td><td style='color:#fd7e14'>&gt; {inc.high_limit}</td></tr>")
    if inc.low_limit is not None:
        limits.append(f"<tr><td style='color:#666'>Warnung-Niedrig</td><td style='color:#fd7e14'>&lt; {inc.low_limit}</td></tr>")
    if inc.low_low_limit is not None:
        limits.append(f"<tr><td style='color:#666'>Kritisch-Niedrig</td><td style='color:#dc3545;font-weight:bold'>&lt; {inc.low_low_limit}</td></tr>")

    flags = []
    if inc.acknowledged:
        flags.append("Quittiert")
    if inc.confirmed:
        flags.append("Bestätigt")
    if inc.reported:
        flags.append("Gemeldet")
    if inc.strict_audited:
        flags.append("Confirm erforderlich")
    flags_str = ", ".join(flags)
    flap_str = f"ALARM FLATTERT {inc.flap_count}x!" if inc.flap_count > 0 else ""

    help_html = ""
    if inc.help:
        help_html = f"<tr><td style='padding:12px 20px;background:#fff3cd;border:1px solid #e0e0e0;border-top:none;font-size:14px'><strong>Handlungsempfehlung:</strong><br>{inc.help}</td></tr>"

    vals = {
        "severity": inc.severity,
        "severity_label": sev_label,
        "severity_bg": sev_color[0],
        "severity_fg": sev_color[1],
        "title": inc.title,
        "source": inc.source,
        "device_name": inc.device_name,
        "room_name": inc.room_name or "-",
        "room_number": inc.room_number,
        "room_contact_name": inc.room_contact_name,
        "room_contact_email": inc.room_contact_email,
        "room_contact_details": inc.room_contact_details,
        "timestamp": inc.timestamp or "-",
        "status": inc.status,
        "id": inc.id,
        "url": inc.url,
        "help": inc.help,
        "t_limits": "\n".join(limits),
        "t_flags": f"<tr><td style='color:#666'>Flags</td><td>{flags_str} {flap_str}</td></tr>" if (flags or flap_str) else "",
        "t_help": help_html,
    }
    return _substitute(template, inc, vals)


def _substitute(template: str, inc: Incident, vals: dict | None = None) -> str:
    if vals is None:
        vals = _build_vals(inc)
    return _do_substitute(template, vals)


def _do_substitute(template: str, vals: dict) -> str:
    class _FormatDict(dict):
        def __missing__(self, key):
            return "{" + key + "}"
    return template.format_map(_FormatDict(vals))


def _build_vals(inc: Incident) -> dict:
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

    return {
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
        "room_name": inc.room_name,
        "room_number": inc.room_number,
        "room_contact_name": inc.room_contact_name,
        "room_contact_email": inc.room_contact_email,
        "room_contact_details": inc.room_contact_details,
    }


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


def email_body_html(inc: Incident, templates_cfg: dict | None = None) -> str:
    tpl = _get_template(templates_cfg, "alert_body_html", _ALERT_BODY_HTML_DEFAULT)
    return _substitute_html(tpl, inc)


def resolved_body_html(inc: Incident, templates_cfg: dict | None = None) -> str:
    tpl = _get_template(templates_cfg, "resolved_body_html", _RESOLVED_BODY_HTML_DEFAULT)
    return _substitute_html(tpl, inc)


def template_variables(inc: Incident) -> dict:
    """Variablen fuer ein freigegebenes WhatsApp-Template (Positionen 1..n)."""
    sev = _SEVERITY_LABEL.get(inc.severity, inc.severity.upper())
    return {
        "1": sev,
        "2": inc.title,
        "3": inc.device_name or inc.source or "-",
        "4": str(inc.id),
    }


def digest_body(incidents: list[Incident], templates_cfg: dict | None = None, total_active: int = 0) -> str:
    lines = [f"DIGEST: {len(incidents)} neue Incidents ({total_active} insgesamt offen)\n"]
    for inc in incidents:
        sev = _SEVERITY_LABEL.get(inc.severity, inc.severity.upper())
        lines.append(f"[{sev}] {inc.title}")
        lines.append(f"  Gerät: {inc.device_name}  |  Raum: {inc.room_name or '-'}")
        lines.append(f"  {inc.url}\n")
    return "\n".join(lines)


def digest_body_html(incidents: list[Incident], templates_cfg: dict | None = None, total_active: int = 0) -> str:
    rows = []
    for inc in incidents:
        color = _SEV_COLORS.get(inc.severity, ("#6c757d", "#fff"))
        sev = _SEVERITY_LABEL.get(inc.severity, inc.severity.upper())
        rows.append(f"""<tr>
<td style="padding:8px 12px;border-bottom:1px solid #e0e0e0;background:{color[0]};color:{color[1]};font-weight:600;font-size:12px;width:80px">{sev}</td>
<td style="padding:8px 12px;border-bottom:1px solid #e0e0e0">{inc.title}</td>
<td style="padding:8px 12px;border-bottom:1px solid #e0e0e0;white-space:nowrap;font-size:12px;color:#666">{inc.device_name}</td>
<td style="padding:8px 12px;border-bottom:1px solid #e0e0e0;white-space:nowrap;font-size:12px;color:#666">{inc.room_name or '-'}</td>
</tr>""")

    return f"""<html><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;margin:0;padding:0">
<table style="width:100%;max-width:700px;border-collapse:collapse" cellpadding="0" cellspacing="0">
<tr><td style="background:#4f46e5;color:#fff;padding:14px 20px;font-size:16px;font-weight:bold">
DIGEST: {len(incidents)} neue Incidents ({total_active} insgesamt offen)
</td></tr>
<tr><td style="padding:0;border:1px solid #e0e0e0;border-top:none">
<table style="width:100%;border-collapse:collapse" cellpadding="0" cellspacing="0">
<tr style="background:#f8f9fa">
<th style="padding:8px 12px;text-align:left;font-size:11px;color:#666;border-bottom:2px solid #ddd">Severity</th>
<th style="padding:8px 12px;text-align:left;font-size:11px;color:#666;border-bottom:2px solid #ddd">Meldung</th>
<th style="padding:8px 12px;text-align:left;font-size:11px;color:#666;border-bottom:2px solid #ddd">Gerät</th>
<th style="padding:8px 12px;text-align:left;font-size:11px;color:#666;border-bottom:2px solid #ddd">Raum</th>
</tr>
{"".join(rows)}
</table>
</td></tr>
<tr><td style="padding:14px 20px;text-align:center;font-size:12px">
<a href="https://lcc.ieu.local/error-history" style="color:#4f46e5;text-decoration:none">Im LCC öffnen</a>
</td></tr>
</table>
</body></html>"""
