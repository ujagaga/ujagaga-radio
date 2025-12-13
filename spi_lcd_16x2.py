#!/usr/bin/env python3

from smbus2 import SMBus
import time

class LCD1602:
    def __init__(self, i2c_addr=0x27, i2c_bus=0):
        self.I2C_ADDR = i2c_addr
        self.I2C_BUS = i2c_bus
        self.MASK_RS = 0x01
        self.MASK_RW = 0x02
        self.MASK_E  = 0x04
        self.MASK_BL = 0x08  # backlight on
        self.bus = SMBus(self.I2C_BUS)

    # Low-level functions
    def _pulse(self, data):
        self.bus.write_byte(self.I2C_ADDR, data | self.MASK_E | self.MASK_BL)
        time.sleep(0.001)
        self.bus.write_byte(self.I2C_ADDR, (data & ~self.MASK_E) | self.MASK_BL)
        time.sleep(0.001)

    def _write_nibble(self, nibble, rs):
        data = (nibble << 4) | (self.MASK_RS if rs else 0)
        self._pulse(data)

    def _write_byte(self, byte, rs):
        self._write_nibble(byte >> 4, rs)
        self._write_nibble(byte & 0x0F, rs)

    # Public functions
    def LCD_init(self):
        time.sleep(0.05)
        for _ in range(3):
            self._write_nibble(0x03, 0)
            time.sleep(0.005)
        self._write_nibble(0x02, 0)  # 4-bit mode

        self._write_byte(0x28, 0)  # Function set: 4-bit, 2 lines
        self._write_byte(0x0C, 0)  # Display ON, cursor off
        self._write_byte(0x06, 0)  # Entry mode: increment cursor
        self.LCD_Clear()
        time.sleep(0.005)

    def LCD_Clear(self):
        self._write_byte(0x01, 0)  # Clear display
        time.sleep(0.005)

    def LCD_SetCursor(self, pos):
        # pos: 0–31
        if pos < 16:
            addr = pos
        elif pos < 32:
            addr = 0x40 + (pos - 16)
        else:
            addr = 0  # default to start
        self._write_byte(0x80 | addr, 0)  # Set DDRAM address

    def LCD_SetCursorBlink(self, enable=True, show_cursor=True):
        """
        enable: True  -> blinking cursor
                False -> no blinking
        show_cursor: underline cursor visible or not
        """
        cmd = 0x08  # base command

        # Display always ON
        cmd |= 0x04

        if show_cursor:
            cmd |= 0x02

        if enable:
            cmd |= 0x01

        self._write_byte(cmd, 0)

    def LCD_Write(self, text):
        for c in text:
            self._write_byte(ord(c), 1)

    def LCD_Backlight(self, on=True):
        self.MASK_BL = 0x08 if on else 0x00

    def close(self):
        self.bus.close()
