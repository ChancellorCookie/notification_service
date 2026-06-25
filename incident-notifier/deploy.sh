#!/usr/bin/env bash
# deploy.sh – Incident Notifier auf Ubuntu installieren/updaten.
# Vorher: gesamten incident-notifier/ Ordner nach /opt/incident-notifier/ kopieren.
# Ausfuehren als root oder mit sudo.
set -euo pipefail

APP_DIR="/opt/incident-notifier"
CONF_DIR="/etc/incident-notifier"
VENV="$APP_DIR/venv"
SVC_NAME="incident-notifier"
SVC_USER="$SVC_NAME"

# --- 1. User anlegen (falls nicht vorhanden) ---
if ! id "$SVC_USER" &>/dev/null; then
    echo "=== Lege System-User '$SVC_USER' an ==="
    useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$SVC_USER"
fi

# --- 2. Verzeichnisse ---
echo "=== Erstelle Verzeichnisse ==="
mkdir -p "$CONF_DIR"

# --- 3. venv + Dependencies ---
echo "=== Python venv + Packages ==="
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$APP_DIR/requirements.txt"

# --- 4. Config + Secrets (nur wenn noch nicht vorhanden) ---
if [ ! -f "$CONF_DIR/config.yaml" ]; then
    echo "=== Lege config.yaml an (bitte danach anpassen!) ==="
    cp "$APP_DIR/config.example.yaml" "$CONF_DIR/config.yaml"
fi
if [ ! -f "$CONF_DIR/secrets.env" ]; then
    echo "=== Lege secrets.env an (bitte danach befuellen!) ==="
    cp "$APP_DIR/secrets.env.example" "$CONF_DIR/secrets.env"
    chmod 600 "$CONF_DIR/secrets.env"
fi

# --- 5. Ownership ---
echo "=== Setze Berechtigungen ==="
chown -R "$SVC_USER:$SVC_USER" "$APP_DIR" "$CONF_DIR"

# --- 6. systemd Unit ---
echo "=== Installiere systemd-Unit ==="
cp "$APP_DIR/incident-notifier.service" /etc/systemd/system/
systemctl daemon-reload

# --- 7. (Re)start ---
if systemctl is-active --quiet "$SVC_NAME"; then
    echo "=== Starte Dienst neu ==="
    systemctl restart "$SVC_NAME"
else
    echo "=== Aktiviere und starte Dienst ==="
    systemctl enable --now "$SVC_NAME"
fi

# --- 8. Status ---
echo ""
echo "============================================"
echo " Deployment abgeschlossen."
echo " Web-UI : http://$(hostname -I | awk '{print $1}'):5080"
echo " Status : systemctl status $SVC_NAME"
echo " Logs   : journalctl -u $SVC_NAME -f"
echo ""
echo " NOCH ZU TUN:"
echo "  1. Config anpassen:  nano $CONF_DIR/config.yaml"
echo "  2. Secrets befuellen: nano $CONF_DIR/secrets.env"
echo "  3. Danach:            systemctl restart $SVC_NAME"
echo "============================================"
