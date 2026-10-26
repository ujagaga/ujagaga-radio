#!/bin/bash
# Install ujagaga-radio as a systemd user service (Raspberry Pi OS / Ubuntu, or Arch / CachyOS).
# Run as the user who will own the radio, from the project folder: ./install_service.sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

if command -v pacman >/dev/null; then
    # venv is part of the python package on Arch
    sudo pacman -S --needed --noconfirm mpd mpc python
else
    sudo apt install -y mpd mpc python3-venv
fi
# The distro mpd package may run its own system-wide mpd; this project starts a private one.
sudo systemctl disable --now mpd.service mpd.socket

python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -r "$DIR/requirements.txt"

mkdir -p ~/.config/systemd/user
sed "s|@DIR@|$DIR|" "$DIR/ujagaga-radio.service" > ~/.config/systemd/user/ujagaga-radio.service

# Start the user's services (PipeWire and the radio) at boot, without logging in.
sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now ujagaga-radio.service

# Source address of the default route (Arch's hostname has no -I)
IP=$(ip route get 1.1.1.1 | awk '{for (i = 1; i < NF; i++) if ($i == "src") print $(i + 1)}')
echo "Radio running at http://$IP:8888"
echo "Logs: journalctl --user -u ujagaga-radio"
