# Incident Notifier

Hintergrunddienst, der die LCC API v2 pollt und neue Incidents per E-Mail (Plaintext + HTML)
an die Laborleitung schickt — angereichert mit Raum- und Kontaktinfos. Die Quittierung
erfolgt direkt im LCC; der Notifier dokumentiert den Eskalationsschritt via `/report`.
Optionale zeitbasierte Erinnerungen, solange ein Vorfall offen bleibt. WhatsApp ist als
zusätzlicher Kanal vorbereitet.

## Konzept

```
LCC API v2 → poll alle 30s → Felder mappen → Raum-Daten anreichern
  → E-Mail (Plaintext + HTML-Tabelle) → /report → SQLite-State
  → bei Verschwinden → optionale Entwarnung
```

Der State (SQLite) verhindert Doppel-Benachrichtigungen über Neustarts hinweg und merkt
sich die letzte Eskalationsstufe. Ein Sendeverlauf (History) ist über die Web-UI einsehbar.

## Was ist neu (v2)

- **OAuth2 Client Credentials** mit Dex/OIDC (Scope + Audience als ein String)
- **HTML-Mails** mit farbiger Severity-Tabelle, Raum/Kontakt-Infos und "Im LCC öffnen"-Button
- **Raum-Anreicherung:** `GET /rooms/` matching über Monitoring-Pfade → `{room_name}`, `{room_contact_name}` etc.
- **Report-Incident:** `POST /lads/alarms/{id}/report` nach erfolgreicher Benachrichtigung
- **Web-UI-Redesign:** Dark Mode, SVG-Icons, Toast-Notifications, Live-Dashboard
- **Sendeverlauf:** Tabelle aller versendeten Nachrichten mit Zeitstempel, Severity, Kanal
- **Crash-Alerting:** E-Mail bei Dienst-Absturz via systemd `OnFailure=`
- **Interaktiver Installer:** `deploy.sh` mit Defaults für Alfahosting-SMTP

## Installation (Ubuntu)

```bash
# Repo nach /opt kopieren
sudo cp -r incident-notifier /opt/incident-notifier

# Interaktiven Installer ausführen
cd /opt/incident-notifier
sudo bash deploy.sh
```

Der Installer fragt alle Werte ab (API-URL, OAuth2-Credentials, SMTP, Eskalation)
und schreibt `/etc/incident-notifier/config.yaml` + `secrets.env`.

### Manuell testen

```bash
cd /opt/incident-notifier
source venv/bin/activate
OAUTH_CLIENT_SECRET="…" SMTP_USER="…" SMTP_PASS="…" python run.py /etc/incident-notifier/config.yaml
```

## Web-UI

Erreichbar unter `http://<host>:5080` nach der Installation:

| Tab | Funktion |
|-----|----------|
| Dashboard | Live-Stats (aktive Incidents, gesendete Nachrichten, letzter Poll) |
| Poll | API-URL, Auth (OAuth2/Bearer/Basic), Interval, Query-Params |
| Kanäle | E-Mail/WhatsApp-Kanäle anlegen, bearbeiten, löschen |
| Eskalation | Severity → Wartezeit → Kanal-Zuordnung |
| Nachrichten | Templates für Betreff, Body (Text + HTML), WhatsApp |
| System | Logging-Level, State-DB-Pfad |
| Sendeverlauf | Chronologische Tabelle aller versendeten Nachrichten |

### Templates

Platzhalter in `{variable}`-Syntax, identisch für Text- und HTML-Templates.
Built-in-Templates werden im Editor angezeigt und können überschrieben werden.
Leeren setzt auf Built-in zurück.

Verfügbare Platzhalter: `{severity}`, `{severity_label}`, `{title}`, `{source}`,
`{device_name}`, `{room_name}`, `{room_number}`, `{room_contact_name}`,
`{room_contact_email}`, `{room_contact_details}`, `{timestamp}`, `{status}`,
`{id}`, `{url}`, `{help}`, `{comment}`, `{flags}`, `{threshold_list}`,
`{flap_warning}`, `{max_severity}`, `{max_severity_label}`, `{active}`,
`{acknowledged}`, `{confirmed}`, `{reported}`, `{strict_audited}`,
`{event_id}`, `{flap_count}`, `{high_high_limit}`, `{high_limit}`,
`{low_limit}`, `{low_low_limit}`

HTML-spezifisch: `{severity_bg}`, `{severity_fg}`, `{t_limits}`, `{t_flags}`, `{t_help}`

## Eskalation

Unter `escalation.stages` definierst du pro Severity Stufen. `after_minutes` ist die
Wartezeit seit der vorigen Stufe, sofern der Vorfall noch im offenen Feed steht.

```yaml
escalation:
  stages:
    error:
      - { after_minutes: 0,  channels: ["email_lab"] }
    warning:
      - { after_minutes: 0,  channels: ["email_lab"] }
      - { after_minutes: 30, channels: ["email_lab"] }
```

## Crash-Alerting

Crash der Dienst unerwartet, triggert systemd `OnFailure=` eine separate Unit
(`incident-notifier-crash-alert.service`), die eine E-Mail mit Hostname,
Zeitstempel und Exit-Code an den ersten konfigurierten E-Mail-Kanal sendet.

## Sicherheit

- Secrets nur in `secrets.env` (chmod 600), nie in der YAML oder im Git
- `${VAR}`-Substitution in der Config für alle sensiblen Werte
- systemd-Unit gehärtet (`ProtectSystem=strict`, `NoNewPrivileges`, `PrivateTmp`)
- Interne TLS-CA über `verify_tls: "/pfad/zur/ca.pem"` möglich

## Erweiterbar

Neuer Kanal: Klasse von `Channel` ableiten, `send(inc, kind)` implementieren,
in `notifier/channels/__init__.py` registrieren (Telegram, Teams, Slack, SMS …).
