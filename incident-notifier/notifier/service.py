"""Hauptdienst: pollt die API, benachrichtigt pro Vorfall, optional mit
zeitbasierter Erinnerung (Eskalation), solange der Vorfall offen bleibt.

Die Quittierung passiert in der Monitoring-Software selbst. Sobald ein Vorfall
dort quittiert/geschlossen ist, taucht er nicht mehr im offenen Feed auf -> der
Dienst stoppt automatisch weitere Erinnerungen und schickt optional eine
Entwarnung. Es gibt KEINE eigene Quittierungs-Erkennung im Dienst.

Robustheit:
- Ein Fehler bei einem einzelnen Incident oder Kanal beendet nicht die Schleife.
- Sende-Versuche werden mit exponentiellem Backoff wiederholt.
- SIGTERM/SIGINT fuehren zu sauberem Shutdown (gut fuer systemd).
"""
import logging
import signal
import time

from .config import load_config
from .poller import Poller
from .state import StateStore
from .channels import build_channel
from .models import Incident

log = logging.getLogger("notifier.service")


def _retry(fn, attempts=3, base_delay=2.0):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if i < attempts - 1:
                time.sleep(base_delay * (2 ** i))
    raise last


class Service:
    def __init__(self, config_path: str):
        self.cfg = load_config(config_path)
        logging.basicConfig(
            level=getattr(logging, self.cfg.get("logging", {}).get("level", "INFO")),
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        self.poller = Poller(self.cfg["poll"])
        state_cfg = self.cfg.get("state", {})
        self.state = StateStore(state_cfg.get("db_path", "./state.db"))

        esc = self.cfg.get("escalation", {})
        self.stages = esc.get("stages", {})
        self.notify_on_resolved = bool(esc.get("notify_on_resolved", False))

        self.channels = {
            name: build_channel(name, ccfg)
            for name, ccfg in self.cfg.get("channels", {}).items()
        }
        self._running = True
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

    def _stop(self, *_):
        log.info("Stop-Signal empfangen, beende ...")
        self._running = False

    def _send(self, inc: Incident, channel_names, kind="alert"):
        any_ok = False
        for cname in channel_names:
            channel = self.channels.get(cname)
            if channel is None:
                log.error("Route verweist auf unbekannten Kanal '%s'", cname)
                continue
            try:
                _retry(lambda: channel.send(inc, kind))
                any_ok = True
                log.info("%s: Incident %s ueber Kanal '%s'", kind, inc.id, cname)
            except Exception as e:  # noqa: BLE001
                log.error("Kanal '%s' fehlgeschlagen fuer %s: %s", cname, inc.id, e)
        return any_ok

    def _stage_channels(self, severity, idx):
        stages = self.stages.get(severity, [])
        return stages[idx]["channels"] if 0 <= idx < len(stages) else []

    def _handle_open(self, inc: Incident):
        stages = self.stages.get(inc.severity, [])
        if not stages:
            log.debug("Keine Stufen fuer Severity '%s', ueberspringe %s", inc.severity, inc.id)
            return
        rec = self.state.get(inc.key)
        now = time.time()

        if rec is None or rec["state"] != "active":
            # Neuer (oder wieder aufgetauchter) Vorfall -> Stufe 0
            if self._send(inc, self._stage_channels(inc.severity, 0)):
                self.state.start(inc, stage=0)
            return

        # Bereits aktiv -> ggf. naechste Erinnerungsstufe, wenn Zeit abgelaufen
        nxt = rec["stage"] + 1
        if nxt < len(stages):
            wait = float(stages[nxt].get("after_minutes", 0)) * 60.0
            if now - rec["stage_sent_at"] >= wait:
                if self._send(inc, self._stage_channels(inc.severity, nxt)):
                    self.state.advance(inc.key, nxt)

    def _handle_disappeared(self):
        """Aktive Vorfaelle, die nicht mehr im offenen Feed sind = quittiert/geschlossen."""
        for rec in self.state.active():
            if rec["key"] in self._open_keys:
                continue
            self.state.set_state(rec["key"], "resolved")
            log.info("Incident %s nicht mehr offen (quittiert/geschlossen)", rec["key"])
            if self.notify_on_resolved:
                inc = Incident(
                    id=rec["key"], title=rec.get("title") or rec["key"],
                    severity=rec.get("severity") or "info", source=rec.get("source") or "",
                )
                self._send(inc, self._stage_channels(inc.severity, 0), kind="resolved")

    def run_once(self):
        incidents = self.poller.fetch()
        self._open_keys = {inc.key for inc in incidents}
        log.debug("%d offene, relevante Incidents abgeholt", len(incidents))
        for inc in incidents:
            self._handle_open(inc)
        self._handle_disappeared()

    def run(self):
        interval = int(self.cfg["poll"].get("interval_seconds", 30))
        log.info("Dienst gestartet (Intervall %ds, Kanaele: %s)",
                 interval, ", ".join(self.channels) or "keine")
        while self._running:
            try:
                self.run_once()
            except Exception as e:  # noqa: BLE001
                log.error("Poll-Zyklus fehlgeschlagen: %s", e)
            slept = 0
            while self._running and slept < interval:
                time.sleep(min(1, interval - slept))
                slept += 1
        self.state.close()
        log.info("Dienst beendet.")
