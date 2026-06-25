"""Erzeugt Kanal-Instanzen anhand des 'type'-Feldes in der Konfiguration."""
from .base import Channel
from .email_channel import EmailChannel
from .whatsapp_twilio import WhatsAppTwilioChannel
from .whatsapp_meta import WhatsAppMetaChannel

_REGISTRY = {
    "email": EmailChannel,
    "whatsapp_twilio": WhatsAppTwilioChannel,
    "whatsapp_meta": WhatsAppMetaChannel,
}


def build_channel(name: str, config: dict, templates_cfg: dict | None = None) -> Channel:
    ctype = config.get("type")
    if ctype not in _REGISTRY:
        raise ValueError(
            f"Unbekannter Kanaltyp '{ctype}' fuer Kanal '{name}'. "
            f"Verfuegbar: {', '.join(_REGISTRY)}"
        )
    return _REGISTRY[ctype](name, config, templates_cfg=templates_cfg)
