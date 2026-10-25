#!/bin/bash
# Install ujagaga-radio as a systemd user service (Raspberry Pi OS Desktop).
# Run as the user who will own the radio, from the project folder: ./install_service.sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

sudo apt install -y mpd mpc python3-venv
# The Debian mpd package runs its own system-wide mpd; this project starts a private one.
sudo systemctl disable --now mpd.service mpd.socket

python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -r "$DIR/requirements.txt"

mkdir -p ~/.config/systemd/user
sed "s|@DIR@|$DIR|" "$DIR/ujagaga-radio.service" > ~/.config/systemd/user/ujagaga-radio.service

# Start the user's services (PipeWire and the radio) at boot, without logging in.
sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now ujagaga-radio.service

echo "Radio running at http://$(hostname -I | awk '{print $1}'):8888"
echo "Logs: journalctl --user -u ujagaga-radio"
