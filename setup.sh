#!/bin/bash

sudo apt install dnsmasq python3-pip python3-dev build-essential libffi-dev i2c-tools mpv

pip3 install setuptools wheel
pip3 install RPLCD smbus2 i2c_lcd 
sudo pip3 install OrangePi.GPIO
