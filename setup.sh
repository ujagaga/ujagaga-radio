#!/bin/bash

sudo apt install dnsmasq python3-pip python3-dev build-essential libffi-dev i2c-tools
sudo apt install mpd mpc xdotool python3-pip python3-dev

pip3 install setuptools wheel
pip3 install Flask RPLCD smbus2 i2c_lcd wheel
sudo pip3 install Flask, OrangePi.GPIO
