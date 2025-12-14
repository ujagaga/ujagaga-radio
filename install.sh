#!/usr/bin/env bash

SERVICE_NAME=ujagaga_radio.service
SERVICE_FILE=/etc/systemd/system/$SERVICE_NAME
USER=root
# --- Installation Section ---
echo "Installing dependencies..."
if ! sudo apt update -y; then
  echo "Error: Failed to update apt repositories. Aborting installation."
  exit 1
fi

if ! sudo apt install -y python3-pip python3-dev build-essential libffi-dev i2c-tools mpv; then
  echo "Error: Failed to install dependencies. Aborting installation."
  exit 1
fi


echo "Installing Python packages..."
pip3 install setuptools wheel 
pip3 install RPLCD smbus2 i2c_lcd OrangePi.GPIO
if [ $? -ne 0 ]; then
  echo "Error: Failed to install python libraries. Aborting installation."
  exit 1
fi


echo "Making run_server.sh executable..."
chmod +x radio.py
if [ $? -ne 0 ]; then
  echo "Error: Failed to make radio.py executable. Aborting installation."
  exit 1
fi

# --- Service File Creation ---
echo "Creating systemd service file: $SERVICE_FILE"
cat <<EOF > "$PWD/$SERVICE_NAME"
[Unit]
Description=Ujagaga_radio
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$USER
ExecStart=/usr/bin/python3 $PWD/radio.py
WorkingDirectory=$PWD
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
if [ $? -ne 0 ]; then
  echo "Error: Failed to create the service file. Aborting installation."
  exit 1
fi
sudo mv "$PWD/$SERVICE_NAME" "$SERVICE_FILE"
if [ $? -ne 0 ]; then
  echo "Error: Failed to move the service file to $SERVICE_FILE. Aborting installation."
  exit 1
fi

# --- Service Management ---
echo "Enabling and starting the service..."
sudo systemctl enable "$SERVICE_NAME"
if [ $? -ne 0 ]; then
  echo "Error: Failed to enable the service. Installation incomplete."
  exit 1
fi
sudo systemctl daemon-reload
if [ $? -ne 0 ]; then
  echo "Error: Failed to start the service. Installation incomplete."
  exit 1
fi

echo "Installation and service started successfully!"

exit 0