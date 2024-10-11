from ..crc64_combine import make_combine_function


class Crc64:
    _POLY = 0x142F0E1EBA9EA3693
    _XOROUT = 0xFFFFFFFFFFFFFFFF

    def __init__(self, init_crc=0):
        from crcmod import Crc

        self.crc64 = Crc(self._POLY, initCrc=init_crc, rev=True, xorOut=self._XOROUT)

        self.crc64_combineFun = make_combine_function(self._POLY, initCrc=init_crc, rev=True, xorOut=self._XOROUT)

    def __call__(self, data):
        self.update(data)

    def update(self, data):
        self.crc64.update(data)

    def combine(self, crc1, crc2, len2):
        return self.crc64_combineFun(crc1, crc2, len2)

    @property
    def crc(self):
        return self.crc64.crcValue


class Crc32:
    _POLY = 0x104C11DB7
    _XOROUT = 0xFFFFFFFF

    def __init__(self, init_crc=0):
        from crcmod import Crc

        self.crc32 = Crc(self._POLY, initCrc=init_crc, rev=True, xorOut=self._XOROUT)

    def __call__(self, data):
        self.update(data)

    def update(self, data):
        self.crc32.update(data)

    @property
    def crc(self):
        return self.crc32.crcValue
