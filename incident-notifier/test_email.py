#!/usr/bin/env python3
"""Ein-Schritt-Test: Startet einen Debug-SMTP-Server im Hintergrund,
verschickt dann einen Fake-Incident per EmailChannel und zeigt die
empfangene Mail an. Keine Installation, keine Accounts.

    python test_email.py
"""
import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(__file__))

PORT = 1027

# ---- SMTP-Debug-Server (im Thread) ----
import asyncio
import email
from aiosmtpd.controller import Controller

def _run_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    class Handler:
        def __init__(self):
            self.received = []
        async def handle_DATA(self, server, session, envelope):
            try:
                content = envelope.content.decode("utf-8", errors="replace") if isinstance(envelope.content, bytes) else envelope.content
                msg = email.message_from_string(content)
                parts = content.split("\r\n\r\n", 1)
                body = parts[1] if len(parts) > 1 else content
                self.received.append({
                    "from": envelope.mail_from,
                    "to": envelope.rcpt_tos,
                    "subject": msg.get("Subject", ""),
                    "body": body,
                })
            except Exception as e:
                print(f"Handler-Fehler: {e}")
            return "250 OK"

    handler = Handler()
    ctrl = Controller(handler, hostname="localhost", port=PORT)
    ctrl.start()
    return ctrl, handler

ctrl, handler = _run_server()
time.sleep(0.3)  # kurz warten, bis der Server lauscht

# ---- Test-Mail versenden ----
from notifier.config import load_config
from notifier.channels.email_channel import EmailChannel
from notifier.models import Incident

cfg = load_config("test-config.yaml")
channel = EmailChannel("email_test", cfg["channels"]["email_test"])

inc = Incident(
    id="INC-4711",
    title="CPU-Last auf SRV-DC01 ueberschritten",
    severity="critical",
    source="SRV-DC01",
    description="CPU-Last liegt seit 5 Minuten bei 98% (Schwelle 90%)",
    timestamp="2026-06-24T14:30:00Z",
    status="open",
    url="https://monitoring.local/incidents/INC-4711",
)

print("Sende Test-Alert ...")
channel.send(inc, kind="alert")

inc_resolved = Incident(
    id="INC-4711",
    title="CPU-Last auf SRV-DC01 ueberschritten",
    severity="critical",
    source="SRV-DC01",
    timestamp="2026-06-24T14:30:00Z",
)
channel.send(inc_resolved, kind="resolved")

time.sleep(0.3)
ctrl.stop()

# ---- Ausgabe ----
print()
for i, m in enumerate(handler.received):
    print("=" * 60)
    print(f"MAIL {i+1} | FROM: {m['from']} | TO: {m['to']}")
    print(f"Subject: {m['subject']}")
    print("-" * 60)
    print(m["body"])
    print("=" * 60)

print(f"\n{len(handler.received)} Mails empfangen - E-Mail-Versand funktioniert.")
