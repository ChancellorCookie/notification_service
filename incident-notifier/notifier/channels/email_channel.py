"""E-Mail-Kanal ueber SMTP (stdlib, keine externe Abhaengigkeit).

Unterstuetzt authentifizierte Relays und offene interne Relays
(username/password leer lassen).
"""
import smtplib
import ssl
from email.message import EmailMessage

from .base import Channel
from .. import formatting
from ..models import Incident


class EmailChannel(Channel):
    def send(self, inc: Incident, kind: str = "alert") -> None:
        c = self.config
        tpl = self.templates_cfg
        if kind == "resolved":
            subject = formatting.resolved_subject(inc, tpl)
            body = formatting.resolved_body(inc, tpl)
        else:
            subject = formatting.email_subject(inc, tpl)
            body = formatting.email_body(inc, tpl)

        msg = EmailMessage()
        msg["From"] = c["from_addr"]
        msg["To"] = ", ".join(c["to_addrs"])
        msg["Subject"] = subject
        msg.set_content(body)

        host = c["smtp_host"]
        port = int(c.get("smtp_port", 587))
        timeout = int(c.get("timeout_seconds", 15))

        if c.get("use_ssl"):  # SMTPS (Port 465)
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx) as s:
                self._auth_and_send(s, c, msg)
        else:
            with smtplib.SMTP(host, port, timeout=timeout) as s:
                if c.get("use_starttls", True):
                    s.starttls(context=ssl.create_default_context())
                self._auth_and_send(s, c, msg)

    @staticmethod
    def _auth_and_send(s, c, msg):
        if c.get("username"):
            s.login(c["username"], c.get("password", ""))
        s.send_message(msg)
