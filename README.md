# ujagaga-radio

A small internet radio controlled from any browser on your network (phone, tablet, PC).
A Flask web app keeps the station list and controls a private [mpd](https://www.musicpd.org/)
instance that plays the streams through PipeWire/PulseAudio.

Built to run on a Raspberry Pi 4 (Raspberry Pi OS Desktop) as a service, but it runs the same
on any Linux desktop with PipeWire.

## Features

- Play / pause a station; the player remembers the last station so it can be resumed.
- Add a station by stream URL, or import a whole `.m3u` playlist (only new URLs are added).
- Export the station list as `.m3u`.
- Delete one station, or tick several and delete them together.
- Mark favourites with a star; favourites are listed first, the rest alphabetically.
- Station names are read from the streams (`icy-name`) at startup and while playing, and saved.
- Volume up/down with a live volume bar (PipeWire default output).
- All open pages update live over a WebSocket.
- SD card friendly: mpd keeps no state, database or log files; the app writes only when
  stations change.

## Requirements

- Linux with PipeWire (or PulseAudio) and `wpctl`
- `mpd`, `mpc`
- Python 3 with `venv`; Python packages are listed in `requirements.txt` (Flask, flask-sock)

## Running on a desktop

```bash
sudo apt install mpd mpc python3-venv
# This project starts its own mpd; the system one is not needed
sudo systemctl disable --now mpd.service mpd.socket

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

./run_radio.sh
```

Open `http://localhost:8888` (or `http://<computer-ip>:8888` from another device).
Stop with Ctrl+C; this also stops mpd.

`run_radio.sh` refuses to start if the radio is already running (port 8888 in use).

## Installing as a service on a Raspberry Pi

Copy the project to the Pi, then run from the project folder, as the user who will own the radio:

```bash
./install_service.sh
```

It installs `mpd`, `mpc` and `python3-venv`, disables the system mpd service, creates `.venv`,
installs `ujagaga-radio.service` as a systemd **user** service and enables lingering, so the
radio (and the user's PipeWire) start at boot without anyone logging in.

Useful commands:

```bash
systemctl --user status ujagaga-radio
systemctl --user restart ujagaga-radio
journalctl --user -u ujagaga-radio      # errors only; normal output is discarded
```

The service restarts the radio automatically. `run_radio.sh` also has a watchdog: if mpd stops
answering (it can hang without exiting) or the web app dies, the script exits so systemd
restarts everything.

## Adding stations

- **+** button: paste a direct stream URL (http or https). The station is added and starts playing.
- **List** button: pick an `.m3u` file. Every new `http(s)` line is added; `#` lines are ignored.
- `sample_playlist.m3u` contains working Serbian stations to start with.

Some stations (HLS `.m3u8` streams) do not send a name and show as "Loading...".

## HTTP control

Besides the web page, the radio can be controlled with plain GET requests:

| Request | Action |
|---|---|
| `/?action=play&id=<id>` | Play station `<id>` |
| `/?action=stop` | Stop (pause) playback |
| `/?action=add&url=<url>` | Add a station and play it |
| `/?action=del&id=<id>` | Delete a station |
| `/?action=del_many&ids=<id>,<id>` | Delete several stations |
| `/?action=favorite&id=<id>` | Toggle favourite |
| `/?action=vol_up`, `/?action=vol_dn` | Volume up / down by 5% |
| `/export.m3u` | Download the station list |

Station ids are database ids. They are shown in the delete button's `data-delete-id` attribute,
and they do not change when other stations are added or removed.

## Files and data

| Path | Purpose |
|---|---|
| `radio.py` | Flask web app and WebSocket |
| `run_radio.sh` | Starts mpd and the web app, watchdog |
| `mpd_local.conf` | Configuration of the private mpd (port 6601, PipeWire output, no state files) |
| `install_service.sh`, `ujagaga-radio.service` | Raspberry Pi service setup |
| `templates/`, `assets/` | Web interface |
| `~/.mpd/stations.db` | Station list, names and favourites (SQLite) |
| `/dev/shm/ujagaga-radio/` | mpd's music database, kept in RAM |

The web interface listens on port **8888**; mpd listens only on `localhost:6601`.
There is no login, so anyone on your network can control the radio. Do not expose port 8888
to the internet.

## Troubleshooting

- **"Radio is already running"**: another copy is running. Stop it first
  (`systemctl --user stop ujagaga-radio` on the Pi).
- **No sound**: check that PipeWire is running (`systemctl --user status pipewire`) and the
  default output with `wpctl status`.
- **A station does not play**: test its URL with `mpc` while the radio runs:
  `MPD_PORT=6601 mpc add <url> && MPD_PORT=6601 mpc play`.
