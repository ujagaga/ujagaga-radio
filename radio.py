#!/usr/bin/env python3

from flask import Flask, request, render_template, send_from_directory, redirect, url_for
from flask_sock import Sock
from simple_websocket import ConnectionClosed
import json
import logging
import os
import sqlite3
import subprocess
import threading
import time
import urllib.request

WEB_PORT = 8888
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
app = Flask(__name__, static_url_path='/assets', static_folder='assets')
app.config['SOCK_SERVER_OPTIONS'] = {'ping_interval': 25}
sock = Sock(app)

# One lock covers reading MPD, commands, and publishing a consistent snapshot.
radio_lock = threading.RLock()
state = None
state_version = 0
last_refresh = 0

# The station list lives here; mpd's queue only holds the station being played.
# Written only when stations change or a name is first learned (few SD card writes).
# All access happens under radio_lock.
db = sqlite3.connect(os.path.expanduser('~/.mpd/stations.db'), check_same_thread=False)
with db:
    db.execute('CREATE TABLE IF NOT EXISTS stations '
               '(id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL UNIQUE, name TEXT, '
               'favorite INTEGER NOT NULL DEFAULT 0)')
    # Databases created before favorites existed lack the column.
    if 'favorite' not in [column[1] for column in db.execute('PRAGMA table_info(stations)')]:
        db.execute('ALTER TABLE stations ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0')
    # One-time import of the list that older versions kept as an mpd playlist.
    old_playlist = os.path.expanduser('~/.mpd/playlists/stations.m3u')
    if not db.execute('SELECT 1 FROM stations').fetchone() and os.path.exists(old_playlist):
        with open(old_playlist) as playlist:
            db.executemany('INSERT OR IGNORE INTO stations (url) VALUES (?)',
                           [(line.strip(),) for line in playlist if line.startswith(('http://', 'https://'))])


def run_process(command_list):
    result = subprocess.run(command_list, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=8, check=True, text=True)
    return result.stdout


def play_station(url):
    run_process(['mpc', 'clear'])
    run_process(['mpc', 'add', url])
    run_process(['mpc', 'play'])


def load_cfg():
    # mpd's queue holds at most the one station last played; it stays there after stop.
    queued = run_process(['mpc', '-f', '%file%\t[%name%]', 'playlist']).split('\n', 1)[0]
    queued_url, _, tag_name = queued.partition('\t')
    if tag_name:
        # Learn the stream's own name once; names already in the database are kept.
        with db:
            db.execute('UPDATE stations SET name = ? WHERE url = ? AND name IS NULL', (tag_name, queued_url))
    playing = run_process(['mpc', 'status', '%state%']).strip() == 'playing'
    stations = []
    last = current = 0
    # Favorites first, then alphabetical; stations without a name yet go last.
    rows = sorted(db.execute('SELECT id, url, name, favorite FROM stations'),
                  key=lambda row: (not row[3], row[2] is None, (row[2] or row[1]).casefold()))
    for station_id, url, name, favorite in rows:
        stations.append({'name': name or 'Loading...', 'href': url, 'id': station_id, 'favorite': bool(favorite)})
        if url == queued_url:
            last = station_id
            current = station_id if playing else 0
    title = run_process(['mpc', 'current']).strip()
    if ': ' in title:
        title = title.split(': ', 1)[1]
    # "Volume: 0.58" -> 58. None hides the bar when PipeWire is not available.
    try:
        volume = round(float(run_process(['wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@']).split()[1]) * 100)
    except (subprocess.SubprocessError, OSError):
        volume = None
    return {'stream_list': stations, 'current': current, 'last': last, 'song_title': title, 'volume': volume}


def fetch_missing_names():
    # Stream servers send the station name in the icy-name header; read it without playing.
    with radio_lock:
        missing = db.execute('SELECT url FROM stations WHERE name IS NULL').fetchall()
    for (url,) in missing:
        try:
            request = urllib.request.Request(url, headers={'Icy-MetaData': '1', 'User-Agent': 'ujagaga-radio'})
            with urllib.request.urlopen(request, timeout=5) as response:
                name = response.headers.get('icy-name')
        except (OSError, ValueError):
            continue
        if not name:
            continue
        # Headers arrive decoded as latin-1; servers actually send UTF-8 or Windows-1252.
        raw = name.encode('latin-1')
        try:
            name = raw.decode('utf-8')
        except UnicodeError:
            name = raw.decode('cp1252', 'replace')
        with radio_lock, db:
            db.execute('UPDATE stations SET name = ? WHERE url = ? AND name IS NULL', (name.strip(), url))


def refresh_state(force=False):
    global state, state_version, last_refresh
    # Called under radio_lock. All clients share at most two MPD reads per second.
    if force or state is None or time.monotonic() - last_refresh >= 0.5:
        updated = load_cfg()
        if updated != state:
            state = updated
            state_version += 1
        last_refresh = time.monotonic()
    return state


def execute_action(data):
    action = data.get('action')
    station_id = int(data.get('id') or 0)
    refresh_state(force=True)
    urls = {station['id']: station['href'] for station in state['stream_list']}
    # Station ids are database ids, so they stay valid when other stations change.
    if action == 'play':
        if station_id not in urls:
            raise ValueError('This station is no longer in the list.')
        play_station(urls[station_id])
    elif action == 'favorite':
        if station_id not in urls:
            raise ValueError('This station is no longer in the list.')
        with db:
            db.execute('UPDATE stations SET favorite = 1 - favorite WHERE id = ?', (station_id,))
    elif action in ('del', 'del_many'):
        ids = {station_id} if action == 'del' else {int(i) for i in str(data.get('ids', '')).split(',') if i}
        if not ids or not ids <= urls.keys():
            raise ValueError('Some selected stations are no longer in the list.')
        with db:
            db.executemany('DELETE FROM stations WHERE id = ?', [(i,) for i in ids])
        # Deleting the playing (or paused) station also drops it from the player.
        if state['last'] in ids:
            run_process(['mpc', 'clear'])
    elif action == 'add':
        url = str(data.get('url', '')).strip().strip('"')
        if not url.startswith(('http://', 'https://')):
            raise ValueError('Enter an http or https radio stream URL.')
        with db:
            db.execute('INSERT OR IGNORE INTO stations (url) VALUES (?)', (url,))
        play_station(url)
    elif action == 'add_playlist':
        # Append stream URLs from an .m3u file, skipping comments and stations already listed.
        lines = [line.strip() for line in str(data.get('playlist', '')).splitlines()]
        new = [url for url in dict.fromkeys(lines)
               if url.startswith(('http://', 'https://')) and url not in urls.values()]
        if not new:
            raise ValueError('No new http or https stream URLs found in the playlist.')
        with db:
            db.executemany('INSERT INTO stations (url) VALUES (?)', [(url,) for url in new])
    elif action == 'stop':
        run_process(['mpc', 'stop'])
    elif action in ('vol_up', 'vol_dn'):
        # PipeWire default output; works without a desktop session. Capped at 100%.
        step = '5%+' if action == 'vol_up' else '5%-'
        run_process(['wpctl', 'set-volume', '-l', '1.0', '@DEFAULT_AUDIO_SINK@', step])
    else:
        raise ValueError('Unknown radio command.')
    refresh_state(force=True)


def state_message():
    return {'type': 'state', 'version': state_version,
            'player_html': render_template('_player.html', **state),
            'stations_html': render_template('_station_list.html', **state)}


@app.route('/', methods=['GET', 'POST'])
def home():
    with radio_lock:
        if request.args.get('action'):
            try:
                execute_action(request.args)
            except (ValueError, subprocess.SubprocessError, OSError) as error:
                return str(error), 400
            return redirect(url_for('home'))
        return render_template('index.html', **refresh_state(force=True))


@sock.route('/ws')
def radio_socket(ws):
    sent_version = -1
    try:
        while True:
            try:
                with radio_lock:
                    refresh_state()
                    if sent_version != state_version:
                        message = state_message()
                        sent_version = state_version
                    else:
                        message = None
                if message:
                    ws.send(json.dumps(message))
            except (subprocess.SubprocessError, OSError):
                # Send a fresh snapshot after MPD recovers, even if unchanged.
                sent_version = -1
                ws.send(json.dumps({'type': 'error', 'message': 'Cannot reach the radio. Retrying…'}))
            raw = ws.receive(timeout=0.2)
            if raw is None:
                continue
            command = None
            try:
                command = json.loads(raw)
                if not isinstance(command, dict):
                    raise ValueError('Invalid radio command.')
                with radio_lock:
                    execute_action(command)
                ws.send(json.dumps({'type': 'ack', 'request_id': command.get('request_id')}))
            except (ValueError, TypeError, subprocess.SubprocessError, OSError) as error:
                message = str(error) if isinstance(error, (ValueError, TypeError)) else 'The radio command failed. Please try again.'
                request_id = command.get('request_id') if isinstance(command, dict) else None
                ws.send(json.dumps({'type': 'error', 'message': message, 'request_id': request_id}))
    except ConnectionClosed:
        pass


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(SCRIPT_PATH, 'assets/favicon.ico', mimetype='image/vnd.microsoft.icon')


if __name__ == '__main__':
    # Skip per-request access log lines; warnings and errors are still shown.
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    threading.Thread(target=fetch_missing_names, daemon=True).start()
    app.run('0.0.0.0', WEB_PORT, threaded=True, debug=False)
