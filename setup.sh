#!/bin/bash

sudo apt install mpd mpc python3-pip python3-dev

python3 -m pip install -r "$(dirname "$0")/requirements.txt"
