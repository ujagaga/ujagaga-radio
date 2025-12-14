#!/usr/bin/env python3

from spi_lcd_16x2 import LCD1602
import fcntl
import struct
from playlist import PLAYLIST
import OPi.GPIO as GPIO
import time
import subprocess
import threading
import socket
import json
import os

BTN_NEXT = 13
BTN_PREV = 11

lcd = LCD1602(i2c_addr=0x27, i2c_bus=0)
ip_message = ""
current_station_id = 0
current_volume = 40
ipc_socket_path = "/tmp/mpvsocket"
mpv_process = None
mpv_lock = threading.Lock()

def get_wifi_ip(iface="wlan0"):
    """
    Returns IPv4 address of the given interface, or None if no IP is assigned.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ifreq = struct.pack("256s", iface.encode("utf-8")[:15])
        res = fcntl.ioctl(sock.fileno(), 0x8915, ifreq)  # SIOCGIFADDR
        return socket.inet_ntoa(res[20:24])
    except OSError:
        return None


def gpio_setup():
    GPIO.setboard(GPIO.ZERO)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BTN_NEXT, GPIO.IN,
               pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_PREV, GPIO.IN,
               pull_up_down=GPIO.PUD_UP)


def start_mpv():
    global mpv_process

    if mpv_process and mpv_process.poll() is None:
        return True

    if os.path.exists(ipc_socket_path):
        os.remove(ipc_socket_path)

    mpv_process = subprocess.Popen([
        "mpv",
        "--idle=yes",
        "--no-video",
        "--really-quiet",
        f"--volume={current_volume}",
        f"--input-ipc-server={ipc_socket_path}"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return wait_for_mpv_ready()


def mpv_ipc_request(cmd):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(ipc_socket_path)
        s.sendall((json.dumps(cmd) + "\n").encode())
        data = s.recv(4096).decode()
        s.close()
        return json.loads(data) if data else None
    except:
        return None


def mpv_get(property_name):
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(ipc_socket_path)

        cmd = {
            "command": ["get_property", property_name],
            "request_id": 1
        }
        client.sendall((json.dumps(cmd) + "\n").encode("utf-8"))

        data = client.recv(4096).decode("utf-8")
        client.close()

        resp = json.loads(data)
        if resp.get("error") == "success":
            return resp.get("data")
    except Exception:
        pass
    return None


def get_song_title():
    title = mpv_get("metadata/by-key/icy-title")
    if title:
        print("T1: ", title.strip())
        return title.strip()

    title = mpv_get("metadata/by-key/title")
    if title:
        print("T2: ", title.strip())
        return title.strip()

    return "  "


def wait_for_mpv_ready(timeout=5):
    start = time.time()
    while time.time() - start < timeout:
        if mpv_process and mpv_process.poll() is not None:
            return False

        if os.path.exists(ipc_socket_path):
            idle = mpv_get("core-idle")
            if idle is True:
                return True

        time.sleep(0.1)
    return False



def wait_for_playback(timeout=5):
    start = time.time()
    while time.time() - start < timeout:
        if mpv_process.poll() is not None:
            return False  # mpv crashed

        playback_time = mpv_get("playback-time")
        idle = mpv_get("core-idle")

        if playback_time and playback_time > 0:
            return True

        if idle is False:
            return True

        time.sleep(0.2)

    return False

def metadata_worker():
    last_title = ""
    while True:
        title = get_song_title()
        if title and title != last_title:
            lcd.LCD_WriteRow(1, title)
            last_title = title
        time.sleep(1)



def try_station(station):
    lcd.LCD_WriteRow(0, station["id"])
    load_url(station["url"])
    return wait_for_playback()


def init():
    global ip_message

    ip = get_wifi_ip("wlan0")
    if ip:
        ip_message = f"{ip}"
    else:
        ip = get_wifi_ip("eth0")
        if ip:
            ip_message = f"{ip}"
        else:
            ip_message = "No WiFi IP"

    lcd.LCD_init()
    lcd.LCD_Backlight(True)
    gpio_setup()
    start_mpv()


def mpv_ipc_command(cmd):
    """Send JSON command to mpv IPC socket."""
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect("/tmp/mpvsocket")
        client.sendall((json.dumps(cmd) + "\n").encode("utf-8"))
        client.close()
    except FileNotFoundError:
        # mpv not running
        pass

def set_volume(vol):
    cmd = {"command": ["set_property", "volume", vol]}
    mpv_ipc_command(cmd)

def load_url(url):
    cmd = {"command": ["loadfile", url, "replace"]}
    mpv_ipc_command(cmd)

def stop():
    cmd = {"command": ["stop"]}
    mpv_ipc_command(cmd)

def volume_up():
    global current_volume
    current_volume = min(100, current_volume + 10)
    set_volume(current_volume)

def volume_down():
    global current_volume
    current_volume = max(0, current_volume - 10)
    set_volume(current_volume)

def next_station():
    global current_station_id
    start_mpv()

    attempts = 0
    while attempts < len(PLAYLIST):
        current_station_id = (current_station_id + 1) % len(PLAYLIST)
        if try_station(PLAYLIST[current_station_id]):
            return
        attempts += 1

    lcd.LCD_WriteRow(0, "No stations")


def previous_station():
    global current_station_id
    start_mpv()
    attempts = 0
    while attempts < len(PLAYLIST):
        current_station_id = (current_station_id - 1) % len(PLAYLIST)
        if try_station(PLAYLIST[current_station_id]):
            return
        attempts += 1

    lcd.LCD_WriteRow(0, "No stations")


def play_radio():
    if start_mpv():
        t = threading.Thread(target=metadata_worker, daemon=True)
        t.start()
        try_station(PLAYLIST[current_station_id])
    else:
        lcd.LCD_WriteRow(0, "mpv failed")

    try:
        while True:
            if not GPIO.input(BTN_NEXT):
                btn_timestamp = time.time()

                long_press_flag = False
                while not GPIO.input(BTN_NEXT):
                    time.sleep(0.1)
                    if time.time() - btn_timestamp > 2:
                        long_press_flag = True
                        press_count = 0
                        volume_up()
                        while not GPIO.input(BTN_NEXT) and press_count < 2:
                            time.sleep(0.5)
                            press_count += 1

                if not long_press_flag:
                    next_station()

            elif not GPIO.input(BTN_PREV):
                btn_timestamp = time.time()

                long_press_flag = False
                while not GPIO.input(BTN_PREV):
                    time.sleep(0.1)
                    if time.time() - btn_timestamp > 2:
                        long_press_flag = True
                        press_count = 0
                        volume_down()
                        while not GPIO.input(BTN_PREV) and press_count < 2:
                            time.sleep(0.5)
                            press_count += 1

                if not long_press_flag:
                    previous_station()

            time.sleep(0.1)

    finally:
        with mpv_lock:
            if mpv_process and mpv_process.poll() is None:
                mpv_process.terminate()
        GPIO.cleanup()

init()
lcd.LCD_WriteRow(0, ip_message)

while ip_message == "":
    time.sleep(1)
    lcd.LCD_WriteRow(0, ip_message)
lcd.LCD_WriteRow(0, ip_message)
time.sleep(5)
play_radio()
lcd.close()
