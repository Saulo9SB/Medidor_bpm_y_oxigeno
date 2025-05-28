# Guarda como ssd1306.py
import framebuf

class SSD1306_I2C:
    def __init__(self, width, height, i2c, addr=0x3c):
        self.width = width
        self.height = height
        self.i2c = i2c
        self.addr = addr
        self.buffer = bytearray(self.height * self.width // 8)
        self.framebuf = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()

    def init_display(self):
        for cmd in (
            b'\xae', b'\xd5\x80', b'\xa8\x3f', b'\xd3\x00', b'\x40', b'\x8d\x14',
            b'\x20\x00', b'\xa1', b'\xc8', b'\xda\x12', b'\x81\xcf', b'\xd9\xf1',
            b'\xdb\x40', b'\xa4', b'\xa6', b'\xaf'):
            self.write_cmd(cmd)

    def write_cmd(self, cmd):
        self.i2c.writeto(self.addr, b'\x00' + cmd)

    def show(self):
        self.write_cmd(b'\x21\x00\x7f')
        self.write_cmd(b'\x22\x00\x07')
        self.i2c.writeto(self.addr, b'\x40' + self.buffer)

    def fill(self, col):
        self.framebuf.fill(col)

    def text(self, string, x, y):
        self.framebuf.text(string, x, y)

    def pixel(self, x, y, col):
        self.framebuf.pixel(x, y, col)
