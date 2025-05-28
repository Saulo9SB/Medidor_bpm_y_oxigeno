from max3010x import MAX3010x

class MAX30102(MAX3010x):
    def __init__(self, i2c, address=0x57):
        super().__init__(i2c, address)
        self.ir = None
        self.red = None

    def read_sensor(self):
        red, ir = self.read_fifo()
        if red is not None and ir is not None:
            self.red = red
            self.ir = ir
            return True
        return False

    def check_part_id(self):
        part_id = self._read(0xFF)[0]
        return part_id == 0x15

