#!/usr/bin/env bash
# deploy.sh – Interaktive Installation des Incident Notifier auf Ubuntu.
# Vorher: gesamten incident-notifier/ Ordner nach /opt/incident-notifier/ kopieren.
# Ausfuehren als root oder mit sudo.
set -euo pipefail

APP_DIR="/opt/incident-notifier"
CONF_DIR="/etc/incident-notifier"
VENV="$APP_DIR/venv"
SVC_NAME="incident-notifier"
SVC_USER="$SVC_NAME"
CONF_FILE="$CONF_DIR/config.yaml"
SECRETS_FILE="$CONF_DIR/secrets.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

say()  { echo -e "${GREEN}==>${NC} $*"; }
warn() { echo -e "${YELLOW}  !${NC} $*"; }
ask()  { read -rp "$(echo -e "  ${CYAN}?${NC} $* ")" "$2"; }
info() { echo -e "    $*"; }

# ---------------------------------------------------------------
echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  Incident Notifier – Installation${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# --- 1. System-User anlegen ---
say "Schritt 1/6: System-User"
if id "$SVC_USER" &>/dev/null; then
    info "User '$SVC_USER' existiert bereits."
else
    useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$SVC_USER"
    info "User '$SVC_USER' angelegt."
fi

# --- 2. Verzeichnisse + venv + Packages ---
say "Schritt 2/6: Python-Umgebung"
mkdir -p "$CONF_DIR"
python3 -m venv "$VENV"
info "venv erstellt – installiere Packages ..."
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$APP_DIR/requirements.txt" -q
info "Fertig."

# --- 3. Monitoring-API ---
echo ""
say "Schritt 3/6: Monitoring-API"

ask "API-URL (z.B. https://lcc.ieu.local/api/v2/incidents):" api_url
api_url=${api_url:-https://lcc.ieu.local/api/v2/incidents}

ask "Auth-Typ (oauth2/bearer/basic/none):" auth_type
auth_type=${auth_type:-oauth2}

if [ "$auth_type" = "oauth2" ]; then
    ask "Token-URL (z.B. https://lcc.ieu.local/oauth/token):" token_url
    token_url=${token_url:-https://lcc.ieu.local/oauth/token}
    ask "Client-ID:" oauth_client_id
    ask "Client-Secret:" oauth_client_secret
    ask "Scope (z.B. openid):" oauth_scope
    ask "Audience (Leer fuer keine):" oauth_audience
elif [ "$auth_type" = "bearer" ]; then
    ask "Bearer-Token:" api_token
elif [ "$auth_type" = "basic" ]; then
    ask "Benutzername:" api_user
    ask "Passwort:" api_pass
fi

ask "TLS verifizieren? (true / Pfad zur CA / false):" tls_verify
tls_verify=${tls_verify:-true}

ask "Incident-URL-Template (z.B. https://lcc.ieu.local/incidents/{id}):" url_tpl
url_tpl=${url_tpl:-https://lcc.ieu.local/incidents/{id}}

ask "Nur diese Severities (Komma-getrennt, z.B. error,alert,warning):" severities
severities=${severities:-error,alert,warning}

ask "Query-Parameter (z.B. lifecycle=open, Leer fuer keine):" query_params
query_params=${query_params:-lifecycle=open}

# --- 4. E-Mail ---
echo ""
say "Schritt 4/6: E-Mail-Kanal"

ask "E-Mail-Kanal aktivieren? (j/N):" enable_email
if [ "${enable_email,,}" = "j" ] || [ "${enable_email,,}" = "ja" ] || [ "${enable_email,,}" = "y" ]; then
    ask "SMTP-Host:" smtp_host
    ask "SMTP-Port (587):" smtp_port
    smtp_port=${smtp_port:-587}
    ask "STARTTLS? (j/N):" starttls
    use_starttls="true"
    [ "${starttls,,}" != "j" ] && [ "${starttls,,}" != "ja" ] && [ "${starttls,,}" != "y" ] && use_starttls="false"
    ask "SMTP-Benutzername:" smtp_user
    ask "SMTP-Passwort:" smtp_pass
    ask "Absender-Adresse (From):" from_addr
    ask "Empfaenger (Komma-getrennt):" to_addrs
else
    info "E-Mail uebersprungen."
fi

# --- 5. WhatsApp (optional) ---
echo ""
say "Schritt 5/6: WhatsApp-Kanal (optional)"

ask "WhatsApp aktivieren? (j/N):" enable_wa
if [ "${enable_wa,,}" = "j" ] || [ "${enable_wa,,}" = "ja" ] || [ "${enable_wa,,}" = "y" ]; then
    ask "Anbieter (twilio/meta):" wa_provider
    wa_provider=${wa_provider:-twilio}
    ask "Empfaenger-Nummern (Komma-getrennt, Format: whatsapp:+49151...):" wa_numbers

    if [ "$wa_provider" = "twilio" ]; then
        ask "Twilio Account SID:" twilio_sid
        ask "Twilio Auth Token:" twilio_token
        ask "Absender-Nummer (whatsapp:+1415...):" wa_from
        ask "Content SID (leer fuer Sandbox/24h):" twilio_content_sid
    else
        ask "Phone Number ID:" meta_phone_id
        ask "Access Token:" meta_token
        ask "Template-Name:" meta_tpl_name
        ask "Template-Sprache (de):" meta_tpl_lang
        meta_tpl_lang=${meta_tpl_lang:-de}
    fi
fi

# --- 6. Eskalation ---
echo ""
say "Schritt 6/6: Eskalation"

ask "Entwarnung bei Verschwinden? (j/N):" notify_resolved
notify_resolved="false"
[ "${notify_resolved,,}" = "j" ] || [ "${notify_resolved,,}" = "ja" ] || [ "${notify_resolved,,}" = "y" ] && notify_resolved="true"

ask "Poll-Intervall in Sekunden (30):" poll_interval
poll_interval=${poll_interval:-30}

ask "Web-UI-Port (5080):" webui_port
webui_port=${webui_port:-5080}

# ---------------------------------------------------------------
# Secrets-Datei schreiben
# ---------------------------------------------------------------
echo ""
say "Schreibe $SECRETS_FILE"

cat > "$SECRETS_FILE" << EOF
# Incident Notifier – Secrets (automatisch generiert)
MONITORING_API_TOKEN=${api_token:-}
SMTP_USER=${smtp_user:-}
SMTP_PASS=${smtp_pass:-}
TWILIO_SID=${twilio_sid:-}
TWILIO_TOKEN=${twilio_token:-}
TWILIO_CONTENT_SID=${twilio_content_sid:-}
META_WA_TOKEN=${meta_token:-}
EOF
chmod 600 "$SECRETS_FILE"
info "Gespeichert."

# ---------------------------------------------------------------
# config.yaml schreiben
# ---------------------------------------------------------------
say "Schreibe $CONF_FILE"

# Severities als YAML-Liste
IFS=',' read -ra sev_arr <<< "$severities"
sev_yaml=""
for s in "${sev_arr[@]}"; do
    s=$(echo "$s" | xargs)
    [ -n "$s" ] && sev_yaml+="  - $s"$'\n'
done

# Query-Params als YAML
qp_yaml=""
if [ -n "$query_params" ]; then
    IFS=',' read -ra qp_arr <<< "$query_params"
    for kv in "${qp_arr[@]}"; do
        kv=$(echo "$kv" | xargs)
        if [[ "$kv" == *"="* ]]; then
            k="${kv%%=*}"
            v="${kv#*=}"
            qp_yaml+="    ${k}: \"${v}\""$'\n'
        fi
    done
fi

# Auth-Block
auth_block=""
if [ "$auth_type" = "oauth2" ]; then
    auth_block="  auth:
    type: oauth2
    token_url: \"${token_url}\"
    client_id: \"${oauth_client_id}\"
    client_secret: \"${oauth_client_secret}\""
    [ -n "${oauth_scope:-}" ] && auth_block+="
    scope: \"${oauth_scope}\""
    [ -n "${oauth_audience:-}" ] && auth_block+="
    audience: \"${oauth_audience}\""
elif [ "$auth_type" = "bearer" ]; then
    auth_block="  auth:
    type: bearer
    token: \${MONITORING_API_TOKEN}"
elif [ "$auth_type" = "basic" ]; then
    auth_block="  auth:
    type: basic
    username: \"${api_user:-}\"
    password: \"${api_pass:-}\""
fi

# E-Mail-Channel
email_channel=""
if [ "${enable_email,,}" = "j" ] || [ "${enable_email,,}" = "ja" ] || [ "${enable_email,,}" = "y" ]; then
    IFS=',' read -ra to_arr <<< "$to_addrs"
    to_yaml=""
    for t in "${to_arr[@]}"; do
        t=$(echo "$t" | xargs)
        [ -n "$t" ] && to_yaml+="      - \"$t\""$'\n'
    done
    email_channel="
  email_lab_lead:
    type: email
    smtp_host: \"${smtp_host}\"
    smtp_port: ${smtp_port}
    use_starttls: ${use_starttls}
    username: \${SMTP_USER}
    password: \${SMTP_PASS}
    from_addr: \"${from_addr}\"
    to_addrs:
${to_yaml}"
fi

# WhatsApp-Channel
wa_channel=""
if [ "${enable_wa,,}" = "j" ] || [ "${enable_wa,,}" = "ja" ] || [ "${enable_wa,,}" = "y" ]; then
    IFS=',' read -ra wa_arr <<< "$wa_numbers"
    wa_to_yaml=""
    for n in "${wa_arr[@]}"; do
        n=$(echo "$n" | xargs)
        [ -n "$n" ] && wa_to_yaml+="      - \"$n\""$'\n'
    done
    if [ "$wa_provider" = "twilio" ]; then
        wa_channel="
  whatsapp_lab_lead:
    type: whatsapp_twilio
    account_sid: \${TWILIO_SID}
    auth_token: \${TWILIO_TOKEN}
    from_number: \"${wa_from}\"
    to_numbers:
${wa_to_yaml}"
        [ -n "${twilio_content_sid:-}" ] && wa_channel+="    content_sid: \${TWILIO_CONTENT_SID}"$'\n'
    else
        wa_channel="
  whatsapp_lab_lead:
    type: whatsapp_meta
    api_version: v21.0
    phone_number_id: \"${meta_phone_id}\"
    access_token: \${META_WA_TOKEN}
    to_numbers:
${wa_to_yaml}    template_name: \"${meta_tpl_name}\"
    template_language: \"${meta_tpl_lang}\""
    fi
fi

# Channel-Liste fuer Eskalation
channel_list=""
[ -n "$email_channel" ] && channel_list="email_lab_lead"
[ -n "$wa_channel" ] && channel_list="${channel_list:+$channel_list, }whatsapp_lab_lead"

# Eskalations-Stufen
esc_block=""
if [ -n "$channel_list" ]; then
    esc_block="escalation:
  notify_on_resolved: ${notify_resolved}
  stages:
    error:
      - { after_minutes: 0, channels: [${channel_list}] }
    alert:
      - { after_minutes: 0, channels: [${channel_list}] }
    warning:
      - { after_minutes: 0, channels: [${channel_list}] }"
fi

channels_block=""
[ -n "$email_channel" ] && channels_block+="$email_channel"$'\n'
[ -n "$wa_channel" ] && channels_block+="$wa_channel"$'\n'

cat > "$CONF_FILE" << EOF
# Incident Notifier – Konfiguration (generiert von deploy.sh)
# Bearbeitbar auch ueber die Web-UI: http://$(hostname -I | awk '{print $1}'):${webui_port}

poll:
  url: "${api_url}"
  method: GET
  interval_seconds: ${poll_interval}
  timeout_seconds: 10
  verify_tls: ${tls_verify}
  incident_url_template: "${url_tpl}"
${auth_block}
${qp_yaml}  pagination:
    page_size: 100
    offset_param: offset
    limit_param: limit
    total_path: meta.items.total
  response:
    items_path: data
    fields:
      id: incidentId
      title: message
      severity: severity
      source: context
      description: message
      timestamp: createdAt
      status: status
      max_severity: maxSeverity
      help: help
      comment: comment
      acknowledged: acknowledged
      confirmed: confirmed
      reported: reported
      flap_count: flapCount
      strict_audited: strictAudited
      active: active
      event_id: eventId
      updated_at: updatedAt
      closed_at: closedAt
      high_high_limit: highHighLimit
      high_limit: highLimit
      low_limit: lowLimit
      low_low_limit: lowLowLimit
  severities:
${sev_yaml}  report_incident:
    enabled: false
    url_template: "{base_url}/lads/alarms/{incident_id}/report"

${esc_block}

channels:${channels_block:+$'\n'${channels_block}}
state:
  db_path: /var/lib/incident-notifier/state.db

logging:
  level: INFO

webui:
  enabled: true
  host: 0.0.0.0
  port: ${webui_port}
EOF

info "Gespeichert."

# ---------------------------------------------------------------
# Berechtigungen + systemd
# ---------------------------------------------------------------
echo ""
say "Setze Berechtigungen + installiere systemd-Unit"

chown -R "$SVC_USER:$SVC_USER" "$APP_DIR" "$CONF_DIR"
cp "$APP_DIR/incident-notifier.service" /etc/systemd/system/
systemctl daemon-reload

if systemctl is-active --quiet "$SVC_NAME"; then
    systemctl restart "$SVC_NAME"
else
    systemctl enable --now "$SVC_NAME"
fi

# ---------------------------------------------------------------
# Fertig
# ---------------------------------------------------------------
IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Installation abgeschlossen!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  Web-UI : ${CYAN}http://${IP}:${webui_port}${NC}"
echo -e "  Status : systemctl status $SVC_NAME"
echo -e "  Logs   : journalctl -u $SVC_NAME -f"
echo ""
echo -e "  Bei Problemen:"
echo -e "    Config  -> nano $CONF_FILE"
echo -e "    Secrets -> nano $SECRETS_FILE"
echo -e "    Neustart -> systemctl restart $SVC_NAME"
echo ""
