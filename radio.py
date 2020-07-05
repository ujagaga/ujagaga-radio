#!/usr/bin/env python3

from flask import Flask, request, render_template, send_from_directory, redirect, url_for
import os
import subprocess
from socket import socket, AF_INET, SOCK_DGRAM

WEB_PORT = 8888
#WEB_PORT = 80 	# Use this as root

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))

app = Flask(__name__, static_url_path='/assets', static_folder='assets')
app.secret_key = 'OCRadio1303153011SecretKey'

url_list = []
current = 0
CMD_PLAY = "play"
CMD_STOP = "stop"
CMD_CLEAR = "clear"
CMD_ADD = "add"
CMD_NEXT = "next"
CMD_LIST = "playlist"
CMD_DEL = "del"
CMD_CURRENT = "current"
CMD_MOVE = "move"

KEY_PLAY = "XF86AudioPlay"
KEY_PAUSE = "XF86AudioPause"
KEY_MUTE = "XF86AudioMute"
KEY_STOP = "XF86AudioStop"
KEY_NEXT = "XF86AudioNext"
KEY_PREV = "XF86AudioPrev"
KEY_SHUT_DOWN = "XF86Close"
KEY_VOL_DOWN = "XF86AudioLowerVolume"
KEY_VOL_UP = "XF86AudioRaiseVolume"
KEY_FORWARD = "XF86Forward"
KEY_REWIND = "XF86Rewind"
KEY_CLOSE = "alt+F4"
KEY_SPACE = "space"
KEY_MEDIA = "XF86AudioMedia"

IP = None
port = 0


def run_process(command_list):
    result = subprocess.run(command_list, stdout=subprocess.PIPE)
    return str(result.stdout, 'utf-8')


def send_key(key):
    run_process(["xdotool", "key", key])


def get_ip():
    ipaddr = ""
    s = socket(AF_INET, SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 0))
        ipaddr = s.getsockname()[0]
    except:
        s.close()
    finally:
        s.close()

    if len(ipaddr.split('.')) != 4:
        return None

    return ipaddr


def get_playlist():
    cmd = ['mpc', CMD_LIST]
    ret_val = run_process(cmd)
    if ret_val.endswith('\n'):
        ret_val = ret_val[:-1]
    return ret_val.split('\n')


def sort_playlist():
    # Get playlist
    temp_list = get_playlist()
    url_list = []
    for item in temp_list:
        url_list.append(item.replace('  ', ' '))

    # Get sorted playlist
    sorted_list = url_list.copy()
    sorted_list.sort()

    print(sorted_list)

    # Check actual positions compared to sorted
    for i in range(0, len(sorted_list)):
        current_id = url_list.index(sorted_list[i])

        if current_id != i:
            # move from current_id to position i. Note that mpc playlist index starts from 1.
            cmd = ['mpc', CMD_MOVE, str(current_id + 1), str(i + 1)]
            run_process(cmd)

            temp_list = get_playlist()
            url_list = []
            for item in temp_list:
                url_list.append(item.replace('  ', ' '))


def load_cfg():
    global url_list
    global current

    # Get playlist
    new_url_list = get_playlist()

    # Populate list to display
    url_list = []
    for i in range(0, len(new_url_list)):
        item = new_url_list[i]
        name = item.split(':')[0]
        if name.startswith('http'):
            name = 'Loading...'

        data = {"name": name, "href": item, "id": len(url_list) + 1}
        url_list.append(data)

    # get currently playing
    current = 0
    cmd = ['mpc']
    status = run_process(cmd).split('\n')

    for i in range(0, len(status)):
        if '[playing]' in status[i]:
            current = int(status[i].split('#')[1].split('/')[0])


@app.route('/', methods=['GET', 'POST'])
def home():
    global current

    load_cfg()

    action = request.args.get('action', '')
    id = int(request.args.get('id', '0'))

    if action == 'add':
        url = request.args.get('url', '').replace('"', '')

        if url != '':

            cmd = ['mpc', CMD_ADD, url]
            run_process(cmd)
            cmd = ['mpc', CMD_PLAY, str(len(url_list) + 1)]
            run_process(cmd)

            load_cfg()

    elif action == 'del':
        if (id > 0) and (id <= len(url_list)):

            cmd = ['mpc', CMD_DEL, str(id)]
            run_process(cmd)

            load_cfg()

    elif action == 'play':
        if (id > 0) and (id <= len(url_list)):

            cmd = ['mpc', CMD_PLAY, str(id)]
            run_process(cmd)

    elif action == 'stop':
        current = 0
        cmd = ['mpc', CMD_STOP]
        run_process(cmd)

    elif action == 'vol_up':
        send_key(KEY_VOL_UP)

    elif action == 'vol_dn':
        send_key(KEY_VOL_DOWN)

    elif action == 'mm_pause':
        send_key(KEY_PAUSE)

    elif action == 'mm_play':
        send_key(KEY_PLAY)

    elif action == 'mm_stop':
        send_key(KEY_SPACE)

    elif action == 'sort':
        sort_playlist()
        load_cfg()

    else:
        cur_cmd = ['mpc', CMD_CURRENT]
        current_text = run_process(cur_cmd)
        print(current_text)
        if len(current_text) > 2:
            try:
                song_title = current_text.split(':')[1]
            except:
                song_title = current_text
        else:
            song_title = ''

        ipaddress = 'http://' + get_ip()

        if WEB_PORT != 80:
            ipaddress += ':{}'.format(WEB_PORT)
        return render_template('index.html', stream_list=url_list, current=current, song_title=song_title, ipaddress=ipaddress)

    return redirect(url_for('home'))


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(SCRIPT_PATH, 'assets/favicon.ico', mimetype='image/vnd.microsoft.icon')


if __name__ == '__main__':
    load_cfg()
    app.run('0.0.0.0', WEB_PORT, threaded=True, debug=False)
