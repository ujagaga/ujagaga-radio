#!/usr/bin/env python3

from spi_lcd_16x2 import LCD1602
import socket
import fcntl
import struct

lcd = LCD1602(i2c_addr=0x27, i2c_bus=0)
ip_message = ""

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


def lcd_write(message = "", cursor_pos = 0):
    try:
        lcd.LCD_SetCursor(cursor_pos)
        lcd.LCD_Write(message)
    finally:
        pass


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

    try:
        lcd.LCD_init()
        lcd.LCD_Backlight(True)
    finally:
        pass

init()
lcd_write(ip_message, 0)
lcd_write("test", 16)
lcd.close()
