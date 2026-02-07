#!/bin/bash
set -e

APP_DIR="/opt/tipe-bssr"
SERVICE_NAME="scrapper"
USER="tipe"

echo "=== Installation TIPE-BSSR Scrapper ==="

# Créer l'utilisateur système
if ! id "$USER" &>/dev/null; then
    echo "Création utilisateur $USER..."
    useradd --system --no-create-home --shell /usr/sbin/nologin "$USER"
fi

# Copier le projet
echo "Copie du projet → $APP_DIR..."
mkdir -p "$APP_DIR"
rsync -a --exclude='venv' --exclude='.git' --exclude='data' --exclude='.idea' "$(dirname "$(dirname "$(realpath "$0")")")/" "$APP_DIR/"
chown -R "$USER:$USER" "$APP_DIR"

# Virtualenv + dépendances
echo "Installation des dépendances..."
apt-get update -qq && apt-get install -y -qq python3 python3-venv > /dev/null
sudo -u "$USER" python3 -m venv "$APP_DIR/venv"
sudo -u "$USER" "$APP_DIR/venv/bin/pip" install -q requests

# Dossier data
mkdir -p "$APP_DIR/data"
chown "$USER:$USER" "$APP_DIR/data"

# Service systemd
echo "Installation du service..."
cp "$APP_DIR/setup/scrapper/$SERVICE_NAME.service" "/etc/systemd/system/"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo "=== Installé ==="
echo "  Status:  systemctl status $SERVICE_NAME"
echo "  Logs:    journalctl -u $SERVICE_NAME -f"
echo "  Stop:    systemctl stop $SERVICE_NAME"
echo "  Data:    $APP_DIR/data/"
