"""Web-UI fuer die Konfiguration des Incident-Notifiers.
Nutzt Flask + Jinja2, laeuft im selben Prozess wie der Poller (Thread).

Aenderungen werden direkt in die config.yaml zurueckgeschrieben.
Nach dem Speichern muss der Dienst neu starten (oder /api/reload aufrufen).
"""
import os
import logging
import yaml
from flask import Flask, render_template, request, redirect, url_for, flash

log = logging.getLogger("notifier.web")

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"))
app.secret_key = os.environ.get("WEBUI_SECRET", "change-me-in-production")


def _config_path():
    return os.environ.get("INCIDENT_NOTIFIER_CONFIG", "/etc/incident-notifier/config.yaml")


def _load():
    with open(_config_path(), "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _save(data: dict):
    path = _config_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# Seiten
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    cfg = _load()
    db_path = cfg.get("state", {}).get("db_path", "./state.db")
    from .state import StateStore
    from datetime import datetime
    state = StateStore(db_path)
    active = state.active()
    history = state.get_history(50)
    state.close()

    for item in history:
        item["sent_at_str"] = datetime.fromtimestamp(item["sent_at"]).strftime("%d.%m.%Y %H:%M:%S")
    stats = {
        "active_incidents": len(active),
        "total_sent": len(history),
        "channels": len(cfg.get("channels", {})),
        "last_time": datetime.fromtimestamp(history[0]["sent_at"]).strftime("%H:%M") if history else "-",
        "last_date": datetime.fromtimestamp(history[0]["sent_at"]).strftime("%d.%m.%Y") if history else "",
        "recent": history[:10],
    }
    return render_template("index.html", cfg=cfg, stats=stats)


@app.route("/poll", methods=["GET", "POST"])
def poll():
    cfg = _load()
    if request.method == "POST":
        _handle_poll_save(cfg)
        flash("Poll-Konfiguration gespeichert.", "success")
        return redirect(url_for("poll"))
    return render_template("poll.html", cfg=cfg.get("poll", {}))


@app.route("/channels", methods=["GET", "POST"])
def channels():
    cfg = _load()
    if request.method == "POST":
        _handle_channels_save(cfg)
        flash("Kanaele gespeichert.", "success")
        return redirect(url_for("channels"))
    return render_template("channels.html", channels=cfg.get("channels", {}))


@app.route("/channels/delete/<name>", methods=["POST"])
def delete_channel(name):
    cfg = _load()
    channels = cfg.get("channels", {})
    if name in channels:
        del channels[name]
        _save(cfg)
        flash(f"Kanal '{name}' gelöscht.", "success")
    else:
        flash(f"Kanal '{name}' nicht gefunden.", "error")
    return redirect(url_for("channels"))


@app.route("/history")
def history():
    from .service import Service
    import os
    db_path = _load().get("state", {}).get("db_path", "/var/lib/incident-notifier/state.db")
    from .state import StateStore
    from datetime import datetime
    state = StateStore(db_path)
    items = state.get_history(200)
    state.close()

    for item in items:
        item["sent_at_str"] = datetime.fromtimestamp(item["sent_at"]).strftime("%d.%m.%Y %H:%M:%S")
    return render_template("history.html", items=items)


@app.route("/escalation", methods=["GET", "POST"])
def escalation():
    cfg = _load()
    if request.method == "POST":
        _handle_escalation_save(cfg)
        flash("Eskalation gespeichert.", "success")
        return redirect(url_for("escalation"))
    esc = cfg.get("escalation", {})
    return render_template("escalation.html", escalation=esc)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    cfg = _load()
    if request.method == "POST":
        cfg["state"] = {"db_path": request.form.get("state_db_path", "./state.db")}
        cfg["logging"] = {"level": request.form.get("logging_level", "INFO")}
        _save(cfg)
        flash("Einstellungen gespeichert.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", cfg=cfg)


@app.route("/templates", methods=["GET", "POST"])
def message_templates():
    cfg = _load()
    if request.method == "POST":
        tpl = cfg.setdefault("templates", {})
        for key in ("alert_subject", "alert_body", "alert_body_html", "resolved_subject", "resolved_body", "resolved_body_html", "whatsapp_text"):
            val = request.form.get(key, "")
            if val.strip():
                tpl[key] = val
            else:
                tpl.pop(key, None)
        _save(cfg)
        flash("Nachrichten-Templates gespeichert.", "success")
        return redirect(url_for("message_templates"))

    from .formatting import PLACEHOLDER_HELP, _ALERT_SUBJECT_DEFAULT, _ALERT_BODY_DEFAULT, _ALERT_BODY_HTML_DEFAULT, _RESOLVED_SUBJECT_DEFAULT, _RESOLVED_BODY_DEFAULT, _RESOLVED_BODY_HTML_DEFAULT, _WHATSAPP_TEXT_DEFAULT
    tpl = cfg.get("templates", {})
    defaults = {
        "alert_subject": _ALERT_SUBJECT_DEFAULT,
        "alert_body": _ALERT_BODY_DEFAULT,
        "alert_body_html": _ALERT_BODY_HTML_DEFAULT,
        "resolved_subject": _RESOLVED_SUBJECT_DEFAULT,
        "resolved_body": _RESOLVED_BODY_DEFAULT,
        "resolved_body_html": _RESOLVED_BODY_HTML_DEFAULT,
        "whatsapp_text": _WHATSAPP_TEXT_DEFAULT,
    }
    return render_template("messages.html", templates=tpl, placeholders=PLACEHOLDER_HELP, defaults=defaults)


# ---------------------------------------------------------------------------
# Form-Handler
# ---------------------------------------------------------------------------

def _parse_textarea(val: str) -> list:
    """Eine Zeile pro Eintrag, leere Zeilen und Kommentare werden ignoriert."""
    items = []
    for line in val.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            items.append(line)
    return items


def _parse_kv_textarea(val: str) -> dict:
    """key=value pro Zeile."""
    result = {}
    for line in val.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        result[k.strip()] = v.strip()
    return result


def _handle_poll_save(cfg: dict):
    poll = cfg.setdefault("poll", {})
    poll["url"] = request.form.get("poll_url", "")
    poll["method"] = request.form.get("poll_method", "GET")
    poll["interval_seconds"] = int(request.form.get("poll_interval", 30))
    poll["timeout_seconds"] = int(request.form.get("poll_timeout", 10))
    v = request.form.get("poll_verify_tls", "true")
    poll["verify_tls"] = True if v.lower() == "true" else False if v.lower() == "false" else v
    poll["incident_url_template"] = request.form.get("incident_url_template", "")

    # Auth
    auth = poll.setdefault("auth", {})
    auth["type"] = request.form.get("auth_type", "none")
    auth["token_url"] = request.form.get("auth_token_url", "")
    auth["client_id"] = request.form.get("auth_client_id", "")
    auth["client_secret"] = request.form.get("auth_client_secret", "")
    auth["scope"] = request.form.get("auth_scope", "")
    auth["audience"] = request.form.get("auth_audience", "")
    auth["token"] = request.form.get("auth_token", "")

    # Query params
    poll["query_params"] = _parse_kv_textarea(request.form.get("query_params", ""))

    # Pagination
    pg = poll.setdefault("pagination", {})
    pg["page_size"] = int(request.form.get("pg_page_size", 0))
    pg["offset_param"] = request.form.get("pg_offset_param", "offset")
    pg["limit_param"] = request.form.get("pg_limit_param", "limit")
    pg["total_path"] = request.form.get("pg_total_path", "")

    # Response fields
    resp = poll.setdefault("response", {})
    resp["items_path"] = request.form.get("resp_items_path", "")
    resp["fields"] = _parse_kv_textarea(request.form.get("resp_fields", ""))

    # Severities
    poll["severities"] = _parse_textarea(request.form.get("severities", ""))

    # Report incident
    report = poll.setdefault("report_incident", {})
    report["enabled"] = request.form.get("report_enabled") == "1"
    report["url_template"] = request.form.get("report_url_template", "")

    # Rooms
    rooms = poll.setdefault("rooms", {})
    rooms["enabled"] = request.form.get("rooms_enabled") == "1"
    rooms["url"] = request.form.get("rooms_url", "")
    rooms["items_path"] = request.form.get("rooms_items_path", "data")
    try:
        rooms["cache_seconds"] = int(request.form.get("rooms_cache_seconds", 300))
    except (ValueError, TypeError):
        rooms["cache_seconds"] = 300

    _save(cfg)


def _handle_channels_save(cfg: dict):
    channels = cfg.setdefault("channels", {})
    new_channels = {}

    # Bestehende Kanaele verarbeiten
    i = 0
    while True:
        prefix = f"ch_{i}_"
        name = request.form.get(f"{prefix}name", "")
        if not name:
            break
        ctype = request.form.get(f"{prefix}type", "")
        ch = {"type": ctype}

        if ctype == "email":
            ch["smtp_host"] = request.form.get(f"{prefix}smtp_host", "")
            ch["smtp_port"] = int(request.form.get(f"{prefix}smtp_port", 587))
            ch["use_ssl"] = request.form.get(f"{prefix}use_ssl") == "1"
            ch["use_starttls"] = request.form.get(f"{prefix}use_starttls") == "1"
            ch["username"] = request.form.get(f"{prefix}username", "")
            ch["password"] = request.form.get(f"{prefix}password", "")
            ch["from_addr"] = request.form.get(f"{prefix}from_addr", "")
            ch["to_addrs"] = _parse_textarea(request.form.get(f"{prefix}to_addrs", ""))
        elif ctype == "whatsapp_twilio":
            ch["account_sid"] = request.form.get(f"{prefix}account_sid", "")
            ch["auth_token"] = request.form.get(f"{prefix}auth_token", "")
            ch["from_number"] = request.form.get(f"{prefix}from_number", "")
            ch["to_numbers"] = _parse_textarea(request.form.get(f"{prefix}to_numbers", ""))
            ch["content_sid"] = request.form.get(f"{prefix}content_sid", "")
        elif ctype == "whatsapp_meta":
            ch["api_version"] = request.form.get(f"{prefix}api_version", "v21.0")
            ch["phone_number_id"] = request.form.get(f"{prefix}phone_number_id", "")
            ch["access_token"] = request.form.get(f"{prefix}access_token", "")
            ch["to_numbers"] = _parse_textarea(request.form.get(f"{prefix}to_numbers", ""))
            ch["template_name"] = request.form.get(f"{prefix}template_name", "")
            ch["template_language"] = request.form.get(f"{prefix}template_language", "de")

        new_channels[name] = ch
        i += 1

    # Neuen Kanal anlegen?
    new_name = request.form.get("new_channel_name", "").strip()
    new_type = request.form.get("new_channel_type", "")
    if new_name and new_type:
        new_channels[new_name] = {"type": new_type}
        # Defaults je nach Typ
        if new_type == "email":
            new_channels[new_name].update({
                "smtp_host": "", "smtp_port": 587, "use_starttls": True,
                "username": "", "password": "", "from_addr": "",
                "to_addrs": [],
            })
        elif new_type == "whatsapp_twilio":
            new_channels[new_name].update({
                "account_sid": "", "auth_token": "", "from_number": "",
                "to_numbers": [], "content_sid": "",
            })
        elif new_type == "whatsapp_meta":
            new_channels[new_name].update({
                "api_version": "v21.0", "phone_number_id": "",
                "access_token": "", "to_numbers": [],
                "template_name": "", "template_language": "de",
            })

    cfg["channels"] = new_channels
    _save(cfg)


def _handle_escalation_save(cfg: dict):
    esc = cfg.setdefault("escalation", {})
    esc["notify_on_resolved"] = request.form.get("notify_on_resolved") == "1"
    esc["immediate"] = [s.strip().lower() for s in request.form.get("immediate", "error, alert").split(",") if s.strip()]
    try:
        esc["digest_interval_minutes"] = int(request.form.get("digest_interval", 60))
    except (ValueError, TypeError):
        esc["digest_interval_minutes"] = 60
    stages = {}
    i = 0
    while True:
        prefix = f"st_{i}_"
        severity = request.form.get(f"{prefix}severity", "")
        if not severity:
            break
        after = int(request.form.get(f"{prefix}after", 0))
        chans = _parse_textarea(request.form.get(f"{prefix}channels", ""))
        if chans:
            stages.setdefault(severity, []).append({
                "after_minutes": after,
                "channels": chans,
            })
        i += 1
    esc["stages"] = stages
    _save(cfg)


# ---------------------------------------------------------------------------
# Start im Hintergrund-Thread
# ---------------------------------------------------------------------------

def start_webui(host="0.0.0.0", port=5080, config_path=None):
    """Startet Flask im Daemon-Thread (blockiert nicht)."""
    if config_path:
        os.environ["INCIDENT_NOTIFIER_CONFIG"] = config_path
    import threading
    t = threading.Thread(target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False), daemon=True)
    t.start()
    log.info("Web-UI gestartet auf http://%s:%d", host, port)
    return t
