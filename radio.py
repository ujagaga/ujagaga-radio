#!/usr/bin/env python3

from flask import Flask, request, render_template, send_from_directory, redirect, url_for
import os
import subprocess
import time

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


def run_process(command_list):
    result = subprocess.run(command_list, stdout=subprocess.PIPE)
    print("Running: {}".format(command_list))

    return str(result.stdout, 'utf-8')


def load_cfg():
    global url_list
    global current

    # Get playlist
    cmd = ['mpc', CMD_LIST]
    ret_val = run_process(cmd)
    if ret_val.endswith('\n'):
        ret_val = ret_val[:-1]
    new_url_list = ret_val.split('\n')
    # print(new_url_list)

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
            cmd = ['mpc', CMD_PLAY]
            run_process(cmd)
            cmd = ['mpc', CMD_ADD, url]
            run_process(cmd)
            cmd = ['mpc', CMD_NEXT]
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
        cmd = ['xdotool', "key", "XF86AudioRaiseVolume"]
        run_process(cmd)

    elif action == 'vol_dn':
        cmd = ['xdotool', "key", "XF86AudioLowerVolume"]
        run_process(cmd)

    else:
        cur_cmd = ['mpc', CMD_CURRENT]
        current_text = run_process(cur_cmd)
        if len(current_text) > 2:
            try:
                song_title = current_text.split(':')[1]
            except:
                song_title = current_text
        else:
            song_title = ''

        return render_template('index.html', stream_list=url_list, current=current, song_title=song_title)

    return redirect(url_for('home'))


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(SCRIPT_PATH, 'assets/favicon.ico', mimetype='image/vnd.microsoft.icon')


if __name__ == '__main__':
    load_cfg()
    app.run('0.0.0.0', WEB_PORT, threaded=True, debug=False)
