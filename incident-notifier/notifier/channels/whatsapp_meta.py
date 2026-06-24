"""WhatsApp-Kanal ueber die offizielle Meta WhatsApp Business Cloud API.

Vorteil gegenueber Twilio: kein Drittanbieter dazwischen, guenstiger bei
hohem Volumen. Nachteil: mehr Einrichtungsaufwand (Meta Business Account,
verifizierte Telefonnummer, freigegebene Templates).

Vom System initiierte Alarme MUESSEN ein freigegebenes Template nutzen
(template_name). Freitext geht nur innerhalb des 24h-Fensters.

Nutzt nur 'requests' (keine zusaetzliche Abhaengigkeit ueber das hinaus,
was der Poller ohnehin braucht).
"""
import requests

from .base import Channel
from .. import formatting
from ..models import Incident


class WhatsAppMetaChannel(Channel):
    def send(self, inc: Incident, kind: str = "alert") -> None:
        c = self.config
        url = f"https://graph.facebook.com/{c.get('api_version', 'v21.0')}/{c['phone_number_id']}/messages"
        headers = {
            "Authorization": f"Bearer {c['access_token']}",
            "Content-Type": "application/json",
        }
        variables = formatting.template_variables(inc)
        for to in c["to_numbers"]:
            if c.get("template_name"):
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "template",
                    "template": {
                        "name": c["template_name"],
                        "language": {"code": c.get("template_language", "de")},
                        "components": [
                            {
                                "type": "body",
                                "parameters": [
                                    {"type": "text", "text": variables[str(i)]}
                                    for i in range(1, len(variables) + 1)
                                ],
                            }
                        ],
                    },
                }
            else:
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": formatting.whatsapp_text(inc)},
                }
            r = requests.post(url, headers=headers, json=payload, timeout=15)
            r.raise_for_status()
