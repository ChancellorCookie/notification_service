#!/usr/bin/env python3
"""Sendet eine Crash-Alert-E-Mail wenn der Dienst unerwartet stoppt.
Aufgerufen von systemd ExecStopPost= mit dem Exit-Status als Argument."""
import sys, os, smtplib, ssl, yaml, socket
from email.message import EmailMessage
from datetime import datetime

CONF = "/etc/incident-notifier/config.yaml"
SECRETS = "/etc/incident-notifier/secrets.env"

def load_env():
    if os.path.exists(SECRETS):
        for line in open(SECRETS):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_env()

def sub_env(v):
    if isinstance(v, str) and "${" in v:
        import re
        return re.sub(r"\$\{([A-Z0-9_]+)\}", lambda m: os.environ.get(m.group(1), ""), v)
    return v

with open(CONF) as f:
    cfg = yaml.safe_load(f) or {}

channels = cfg.get("channels", {})
if not channels:
    print("Keine Kanäle konfiguriert", file=sys.stderr)
    sys.exit(0)

name, ch = next(iter(channels.items()))
if ch.get("type") != "email":
    print(f"Kanal '{name}' ist kein E-Mail-Kanal", file=sys.stderr)
    sys.exit(1)

exit_status = sys.argv[1] if len(sys.argv) > 1 else "unknown"
hostname = socket.gethostname()
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

msg = EmailMessage()
msg["From"] = sub_env(ch.get("from_addr", ""))
msg["To"] = ", ".join(ch.get("to_addrs", []))
msg["Subject"] = f"[CRASH] Incident Notifier auf {hostname} gestoppt (Exit {exit_status})"
msg.set_content(f"""Der Incident Notifier auf {hostname} wurde unerwartet beendet.

Zeitpunkt: {now}
Exit-Code: {exit_status}

Bitte den Dienst überprüfen:
  systemctl status incident-notifier
  journalctl -u incident-notifier -n 50
""")

user = sub_env(ch.get("username", ""))
pw = sub_env(ch.get("password", ""))
host = ch.get("smtp_host", "")
port = int(ch.get("smtp_port", 587))

try:
    if ch.get("use_ssl"):
        ctx = ssl.create_default_context()
        s = smtplib.SMTP_SSL(host, port, timeout=10, context=ctx)
    else:
        s = smtplib.SMTP(host, port, timeout=10)
        if ch.get("use_starttls", True):
            s.starttls(context=ssl.create_default_context())
    if user:
        s.login(user, pw)
    s.send_message(msg)
    s.quit()
    print(f"Crash-Alert gesendet an {msg['To']}")
except Exception as e:
    print(f"Fehler beim Senden: {e}", file=sys.stderr)
    sys.exit(1)
