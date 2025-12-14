#!/usr/bin/env python3

from smbus2 import SMBus
import time
import threading


class LCD1602:
    def __init__(self, i2c_addr=0x27, i2c_bus=0):
        self.I2C_ADDR = i2c_addr
        self.I2C_BUS = i2c_bus
        self.MASK_RS = 0x01
        self.MASK_RW = 0x02
        self.MASK_E  = 0x04
        self.MASK_BL = 0x08  # backlight on

        self.bus = SMBus(self.I2C_BUS)

        # --- Text buffers ---
        self.row_text = ["", ""]
        self.row_offset = [0, 0]

        # --- Threading ---
        self._lock = threading.Lock()
        self._running = True
        self._scroll_thread = threading.Thread(
            target=self._scroll_worker,
            daemon=True
        )

    # ------------------------------------------------------------------
    # Low-level functions
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # LCD control
    # ------------------------------------------------------------------

    def LCD_init(self):
        time.sleep(0.05)
        for _ in range(3):
            self._write_nibble(0x03, 0)
            time.sleep(0.005)
        self._write_nibble(0x02, 0)  # 4-bit mode

        self._write_byte(0x28, 0)  # 4-bit, 2 lines
        self._write_byte(0x0C, 0)  # display on, cursor off
        self._write_byte(0x06, 0)  # entry mode
        self.LCD_Clear()

        # Start scrolling thread
        self._scroll_thread.start()

    def LCD_Clear(self):
        with self._lock:
            self._write_byte(0x01, 0)
            self.row_text = ["", ""]
            self.row_offset = [0, 0]
        time.sleep(0.005)

    def LCD_SetCursor(self, row, x_pos):
        x_pos = max(0, min(15, x_pos))
        addr = x_pos if row == 0 else 0x40 + x_pos
        self._write_byte(0x80 | addr, 0)

    def LCD_SetCursorBlink(self, enable=True, show_cursor=True):
        cmd = 0x08 | 0x04  # display ON
        if show_cursor:
            cmd |= 0x02
        if enable:
            cmd |= 0x01
        self._write_byte(cmd, 0)

    def LCD_Backlight(self, on=True):
        self.MASK_BL = 0x08 if on else 0x00

    # ------------------------------------------------------------------
    # High-level text API (NEW)
    # ------------------------------------------------------------------

    def LCD_WriteRow(self, row, text):
        """
        Write text to row buffer.
        If text > 16 chars, scrolling is enabled automatically.
        """
        if row not in (0, 1):
            return

        with self._lock:
            self.row_text[row] = text
            self.row_offset[row] = 0
            self._render_row(row)

    def _render_row(self, row):
        text = self.row_text[row]
        offset = self.row_offset[row]

        if len(text) <= 16:
            visible = text.ljust(16)
        else:
            padded = text + "   "
            start = offset % len(padded)
            visible = (padded + padded)[start:start + 16]

        self.LCD_SetCursor(row, 0)
        for c in visible:
            self._write_byte(ord(c), 1)

    # ------------------------------------------------------------------
    # Scrolling thread
    # ------------------------------------------------------------------

    def _scroll_worker(self):
        while self._running:
            time.sleep(0.5)
            with self._lock:
                for row in (0, 1):
                    if len(self.row_text[row]) > 16:
                        self.row_offset[row] += 1
                        self._render_row(row)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        self._running = False
        time.sleep(0.6)
        self.bus.close()
