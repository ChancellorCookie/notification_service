"""WhatsApp-Kanal ueber Twilio.

Twilio ist der schnellste Weg zu einer funktionierenden WhatsApp-Meldung.
Wichtig fuer den Produktivbetrieb: WhatsApp erlaubt vom System initiierte
Nachrichten (also Incident-Alarme, ohne dass der Empfaenger vorher
geschrieben hat) NUR ueber ein vorab freigegebenes Template.

- Ohne content_sid: Freitext. Funktioniert nur in der Twilio-Sandbox oder
  innerhalb von 24h nach einer Empfaenger-Nachricht.
- Mit content_sid: freigegebenes Template (Pflicht fuer echte Alarme).

Abhaengigkeit: pip install twilio
"""
from .base import Channel
from .. import formatting
from ..models import Incident


class WhatsAppTwilioChannel(Channel):
    def __init__(self, name, config, templates_cfg=None):
        super().__init__(name, config, templates_cfg)
        from twilio.rest import Client
        self._client = Client(config["account_sid"], config["auth_token"])

    def send(self, inc: Incident, kind: str = "alert") -> None:
        c = self.config
        tpl = self.templates_cfg
        for to in c["to_numbers"]:
            kwargs = {"from_": c["from_number"], "to": to}
            if c.get("content_sid"):
                import json
                kwargs["content_sid"] = c["content_sid"]
                kwargs["content_variables"] = json.dumps(
                    formatting.template_variables(inc)
                )
            else:
                kwargs["body"] = formatting.whatsapp_text(inc, tpl)
            self._client.messages.create(**kwargs)
