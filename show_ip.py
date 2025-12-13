#!/usr/bin/env python3

from spi_lcd_16x2 import LCD1602
import socket
import fcntl
import struct

def get_wifi_ip(iface="wlan0"):
    """
    Returns IPv4 address of the given interface, or None if no IP is assigned.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ifreq = struct.pack("256s", iface.encode("utf-8")[:15])
        res = fcntl.ioctl(sock.fileno(), 0x8915, ifreq)  # SIOCGIFADDR
        ip = socket.inet_ntoa(res[20:24])
        return ip
    except OSError:
        return None


lcd = LCD1602(i2c_addr=0x27, i2c_bus=0)

ip = get_wifi_ip("wlan0")
if ip:
    ip_message = f"IP: {ip}"
    print("WiFi IP:", ip)
else:
    ip_message = "No WiFi IP"
    print("No WiFi IP assigned")

try:
    lcd.LCD_init()
    lcd.LCD_Backlight(True)

    lcd.LCD_SetCursor(0)
    lcd.LCD_Write(ip_message)

finally:
    lcd.close()

