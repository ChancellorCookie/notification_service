"""Hauptdienst: pollt die API, benachrichtigt pro Vorfall, optional mit
zeitbasierter Erinnerung (Eskalation), solange der Vorfall offen bleibt.

Hybrid-Modus: ERROR/ALERT sofort, WARNING/INFO/NOTICE im Digest (gebündelt).
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

_IMMEDIATE_DEFAULT = ["error", "alert"]
_DIGEST_INTERVAL_DEFAULT = 60


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
        self.config_path = config_path
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

        self.immediate = [s.lower() for s in esc.get("immediate", _IMMEDIATE_DEFAULT)]
        self.digest_interval = int(esc.get("digest_interval_minutes", _DIGEST_INTERVAL_DEFAULT))
        self._last_digest = 0.0

        self.channels = {
            name: build_channel(name, ccfg, templates_cfg=self.cfg.get("templates", {}))
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
                self.state.log_send(inc.id, cname, kind, inc.title, inc.severity)
                log.info("%s: Incident %s ueber Kanal '%s'", kind, inc.id, cname)
            except Exception as e:  # noqa: BLE001
                log.error("Kanal '%s' fehlgeschlagen fuer %s: %s", cname, inc.id, e)
        return any_ok

    def _all_channels(self):
        ch = list(self.channels.keys())
        if ch:
            return ch
        stages_ch = set()
        for sev_stages in self.stages.values():
            for s in sev_stages:
                stages_ch.update(s.get("channels", []))
        return list(stages_ch)

    def _stage_channels(self, severity, idx):
        stages = self.stages.get(severity, [])
        return stages[idx]["channels"] if 0 <= idx < len(stages) else []

    def _is_immediate(self, severity: str) -> bool:
        return severity.lower() in self.immediate

    def _handle_open(self, inc: Incident):
        rec = self.state.get(inc.id)
        if rec is not None and rec["state"] == "active":
            return

        if self._is_immediate(inc.severity):
            self._handle_immediate(inc)
        else:
            self._handle_digest_track(inc)

    def _handle_immediate(self, inc: Incident):
        stages = self.stages.get(inc.severity, [])
        if not stages:
            channels = self._all_channels()
            if channels:
                if self._send(inc, channels):
                    self.state.start(inc, stage=0)
                    if not inc.reported:
                        self.poller.report_incident(inc.id, comment=f"Eskaliert per {', '.join(channels)}")
            else:
                self.state.start(inc, stage=0)
            return

        if self._send(inc, self._stage_channels(inc.severity, 0)):
            self.state.start(inc, stage=0)
            if not inc.reported:
                self.poller.report_incident(inc.id, comment=f"Eskaliert per {', '.join(self._stage_channels(inc.severity, 0))}")

    def _handle_digest_track(self, inc: Incident):
        rec = self.state.get(inc.id)
        if rec is None or rec["state"] != "active":
            self.state.start_digest(inc)
            if not inc.reported:
                self.poller.report_incident(inc.id, comment="Für Digest vorgemerkt")
            log.info("Incident %s (%s) fuer Digest vorgemerkt", inc.id, inc.severity)

    def _send_digest(self):
        pending = self.state.digest_pending()
        if not pending:
            return

        all_ch = self._all_channels()
        if not all_ch:
            return

        incidents = [self._rec_to_inc(r) for r in pending]
        log.info("Sende Digest mit %d Incidents", len(incidents))
        self.state.mark_digest_sent()
        total_active = len(self.state.active())

        from . import formatting
        for cname in all_ch:
            channel = self.channels.get(cname)
            if channel is None:
                continue
            try:
                channel.send_digest(incidents, total_active)
                for inc in incidents:
                    self.state.log_send(inc.id, cname, "digest", inc.title, inc.severity)
                log.info("Digest mit %d Incidents ueber Kanal '%s'", len(incidents), cname)
            except Exception as e:
                log.error("Digest-Kanal '%s' fehlgeschlagen: %s", cname, e)

    def _rec_to_inc(self, rec: dict) -> Incident:
        return Incident(
            id=rec["key"], title=rec.get("title") or rec["key"],
            severity=rec.get("severity") or "info", source=rec.get("source") or "",
        )

    def _handle_disappeared(self):
        for rec in self.state.active():
            if rec["key"] in self._open_keys:
                continue
            self.state.set_state(rec["key"], "resolved")
            log.info("Incident %s nicht mehr offen (quittiert/geschlossen)", rec["key"])
            if self.notify_on_resolved:
                inc = self._rec_to_inc(rec)
                channels = self._stage_channels(inc.severity, 0)
                if not channels:
                    channels = self._all_channels()
                if channels:
                    remaining = len([r for r in self.state.active() if r["key"] != rec["key"]])
                    for cname in channels:
                        channel = self.channels.get(cname)
                        if channel:
                            try:
                                channel.send_resolved(inc, remaining)
                                self.state.log_send(inc.id, cname, "resolved", inc.title, inc.severity)
                            except Exception as e:
                                log.error("Resolved-Kanal '%s' fehlgeschlagen: %s", cname, e)

    def run_once(self):
        incidents = self.poller.fetch()
        self._open_keys = {inc.id for inc in incidents}
        log.debug("%d offene, relevante Incidents abgeholt", len(incidents))
        for inc in incidents:
            self._handle_open(inc)
        self._handle_disappeared()

        now = time.time()
        if now - self._last_digest >= self.digest_interval * 60:
            self._send_digest()
            self._last_digest = now

    def run(self):
        interval = int(self.cfg["poll"].get("interval_seconds", 30))
        log.info("Dienst gestartet (Intervall %ds, Digest alle %dmin, Kanaele: %s)",
                 interval, self.digest_interval, ", ".join(self.channels) or "keine")

        webui = self.cfg.get("webui", {})
        if webui.get("enabled", True):
            from .web import start_webui
            start_webui(
                host=webui.get("host", "0.0.0.0"),
                port=int(webui.get("port", 5080)),
                config_path=self.config_path,
            )

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
