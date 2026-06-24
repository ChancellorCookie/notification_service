"""Einheitliche Formatierung der Benachrichtigungstexte."""
from .models import Incident

_EMOJI = {"critical": "\U0001F6A8", "warning": "\u26A0\uFE0F", "info": "\u2139\uFE0F"}


def email_subject(inc: Incident) -> str:
    return f"[{inc.severity.upper()}] {inc.title}"


def email_body(inc: Incident) -> str:
    lines = [
        f"Severity:    {inc.severity}",
        f"Titel:       {inc.title}",
        f"Quelle:      {inc.source or '-'}",
        f"Zeitpunkt:   {inc.timestamp or '-'}",
        f"Status:      {inc.status}",
        f"Incident-ID: {inc.id}",
    ]
    if inc.url:
        lines += ["", f"Zum Quittieren oeffnen: {inc.url}"]
    if inc.description:
        lines += ["", "Beschreibung:", inc.description]
    return "\n".join(lines)


def whatsapp_text(inc: Incident) -> str:
    """Freitext fuer das 24h-Fenster / die Twilio-Sandbox.

    Fuer den Produktivbetrieb ausserhalb des 24h-Fensters wird stattdessen
    ein freigegebenes Template mit Variablen verwendet (siehe README).
    """
    emoji = _EMOJI.get(inc.severity, "")
    parts = [
        f"{emoji} {inc.severity.upper()} Incident",
        inc.title,
        f"Quelle: {inc.source}" if inc.source else None,
        inc.description or None,
        f"Zeit: {inc.timestamp}" if inc.timestamp else None,
        inc.url or None,
        f"ID: {inc.id}",
    ]
    return "\n".join(p for p in parts if p)


def resolved_subject(inc: Incident) -> str:
    return f"[ENTWARNUNG] {inc.title}"


def resolved_body(inc: Incident) -> str:
    return "\n".join(
        [
            "Der folgende Vorfall ist nicht mehr offen (quittiert oder geschlossen):",
            "",
            f"Titel:       {inc.title}",
            f"Quelle:      {inc.source or '-'}",
            f"Incident-ID: {inc.id}",
        ]
    )


def template_variables(inc: Incident) -> dict:
    """Variablen fuer ein freigegebenes WhatsApp-Template (Positionen 1..n)."""
    return {"1": inc.severity, "2": inc.title, "3": inc.source or "-", "4": str(inc.id)}
