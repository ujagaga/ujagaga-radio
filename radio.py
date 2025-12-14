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


BTN_NEXT = 11
BTN_PREV = 13
# BTN_VOLUP = 19
# BTN_VOLDOWN = 18

lcd = LCD1602(i2c_addr=0x27, i2c_bus=0)
ip_message = ""
current_station_id = 0
current_volume = 20
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


def start_mpv(url):
    """Start mpv process with IPC socket."""
    global mpv_process
    if mpv_process is None or mpv_process.poll() is not None:
        # Remove old socket if exists
        if os.path.exists(ipc_socket_path):
            os.remove(ipc_socket_path)
        mpv_process = subprocess.Popen([
            "mpv",
            "--no-video",
            "--really-quiet",
            f"--volume={current_volume}",
            f"--input-ipc-server={ipc_socket_path}",
            url
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Wait briefly to allow socket creation
        time.sleep(0.5)
    else:
        load_url(url)


def init():
    global ip_message

    ip = get_wifi_ip("wlan0")
    if ip:
        ip_message = f"IP ADDRESS OF WIFI: {ip}"
    else:
        ip = get_wifi_ip("eth0")
        if ip:
            ip_message = f"{ip}"
        else:
            ip_message = "No WiFi IP"

    lcd.LCD_init()
    lcd.LCD_Backlight(True)
    gpio_setup()

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

def play_station(station_url, label):
    lcd.LCD_WriteRow(1, label)
    start_mpv(station_url)

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

    if current_station_id < (len(PLAYLIST) - 1):
        current_station_id = current_station_id + 1
    else:
        current_station_id = 0

    station = PLAYLIST[current_station_id]
    play_station(station.get("url"), station.get("id"))


def previous_station():
    global current_station_id

    if current_station_id > 0:
        current_station_id = current_station_id - 1
    else:
        current_station_id = len(PLAYLIST)-1

    station = PLAYLIST[current_station_id]
    play_station(station.get("url"), station.get("id"))


def play_radio():
    station = PLAYLIST[current_station_id]
    play_station(station.get("url"), station.get("id"))
    try:
        while True:
            if not GPIO.input(BTN_NEXT):
                btn_timestamp = time.time()

                long_press_flag = False
                while not GPIO.input(BTN_NEXT):
                    time.sleep(0.1)
                    if time.time() - btn_timestamp > 2:
                        long_press_flag = True
                        while not GPIO.input(BTN_NEXT):
                            time.sleep(1)
                            volume_up()

                if not long_press_flag:
                    next_station()

            elif not GPIO.input(BTN_PREV):
                btn_timestamp = time.time()

                long_press_flag = False
                while not GPIO.input(BTN_PREV):
                    time.sleep(0.1)
                    if time.time() - btn_timestamp > 2:
                        long_press_flag = True
                        while not GPIO.input(BTN_PREV):
                            time.sleep(1)
                            volume_down()

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
play_radio()
lcd.close()
