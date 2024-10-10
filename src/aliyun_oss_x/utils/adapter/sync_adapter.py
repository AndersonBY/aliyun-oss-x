import os.path
import logging
from typing import Callable, Iterable

import crcmod

from ...compat import to_bytes
from ...exceptions import ClientError
from ...crc64_combine import make_combine_function
from ...types import SyncReadableBuffer, ObjectDataType, is_readable_buffer_sync, has_crc_attr


logger = logging.getLogger(__name__)


class SizedFileAdapter:
    """通过这个适配器（Adapter），可以把原先的 `file_object` 的长度限制到等于 `size`。"""

    def __init__(self, file_object: SyncReadableBuffer, size: int):
        self.file_object = file_object
        self.size = size
        self.offset = 0

    def read(self, amt=None):
        if self.offset >= self.size:
            return b""

        if (amt is None or amt < 0) or (amt + self.offset >= self.size):
            data = self.file_object.read(self.size - self.offset)
            self.offset = self.size
            return data

        self.offset += amt
        return self.file_object.read(amt)

    @property
    def len(self):
        return self.size


def file_object_remaining_bytes(fileobj):
    current = fileobj.tell()

    fileobj.seek(0, os.SEEK_END)
    end = fileobj.tell()
    fileobj.seek(current, os.SEEK_SET)

    return end - current


def _has_data_size_attr(data):
    return hasattr(data, "__len__") or hasattr(data, "len") or (hasattr(data, "seek") and hasattr(data, "tell"))


def _get_data_size(data):
    if hasattr(data, "__len__"):
        return len(data)

    if hasattr(data, "len"):
        return data.len

    if hasattr(data, "seek") and hasattr(data, "tell"):
        return file_object_remaining_bytes(data)

    return None


_CHUNK_SIZE = 8 * 1024


def make_progress_adapter(
    data: ObjectDataType, progress_callback: Callable[[int, int | None], None] | None, size=None
):
    """返回一个适配器，从而在读取 `data` ，即调用read或者对其进行迭代的时候，能够
     调用进度回调函数。当 `size` 没有指定，且无法确定时，上传回调函数返回的总字节数为None。

    :param data: 可以是bytes、file object或iterable
    :param progress_callback: 进度回调函数，参见 :ref:`progress_callback`
    :param size: 指定 `data` 的大小，可选

    :return: 能够调用进度回调函数的适配器
    """
    data = to_bytes(data)

    if size is None:
        size = _get_data_size(data)

    if not size:
        if is_readable_buffer_sync(data):
            return _FileLikeAdapter(data, progress_callback)
        elif isinstance(data, Iterable):
            return _IterableAdapter(data, progress_callback)
        else:
            raise ClientError(f"{data.__class__.__name__} is not a file object, nor an iterator")
    else:
        return _BytesAndFileAdapter(data, progress_callback, size)


def make_crc_adapter(data: ObjectDataType, init_crc=0, discard=0):
    """返回一个适配器，从而在读取 `data` ，即调用read或者对其进行迭代的时候，能够计算CRC。

    :param discard:
    :return:
    :param data: 可以是bytes、file object或iterable
    :param init_crc: 初始CRC值，可选

    :return: 能够调用计算CRC函数的适配器
    """
    data = to_bytes(data)

    # bytes or file object
    if _has_data_size_attr(data):
        if discard:
            raise ClientError("Bytes of file object adapter does not support discard bytes")
        return _BytesAndFileAdapter(data, size=_get_data_size(data), crc_callback=Crc64(init_crc))
    # file-like object
    elif is_readable_buffer_sync(data):
        return _FileLikeAdapter(data, crc_callback=Crc64(init_crc), discard=discard)
    # iterator
    elif isinstance(data, Iterable):
        if discard:
            raise ClientError("Iterator adapter does not support discard bytes")
        return _IterableAdapter(data, crc_callback=Crc64(init_crc))
    else:
        raise ClientError(f"{data.__class__.__name__} is not a file object, nor an iterator")


def make_cipher_adapter(data: ObjectDataType, cipher_callback, discard: int = 0):
    """返回一个适配器，从而在读取 `data` ，即调用read或者对其进行迭代的时候，能够进行加解密操作。

    :param encrypt:
    :param cipher_callback:
    :param discard: 读取时需要丢弃的字节
    :param data: 可以是bytes、file object或iterable

    :return: 能够客户端加密函数的适配器
    """
    data = to_bytes(data)

    # bytes or file object
    if _has_data_size_attr(data):
        if discard:
            raise ClientError("Bytes of file object adapter does not support discard bytes")
        return _BytesAndFileAdapter(data, size=_get_data_size(data), cipher_callback=cipher_callback)
    if is_readable_buffer_sync(data):
        return _FileLikeAdapter(data, cipher_callback=cipher_callback, discard=discard)
    # iterator
    elif isinstance(data, Iterable):
        if discard:
            raise ClientError("Iterator adapter does not support discard bytes")
        return _IterableAdapter(data, cipher_callback=cipher_callback)
    else:
        raise ClientError(f"{data.__class__.__name__} is not a file object")


def _invoke_crc_callback(crc_callback, content, discard=0):
    if crc_callback:
        crc_callback(content[discard:])


def _invoke_progress_callback(
    progress_callback: Callable[[int, int | None], None] | None, consumed_bytes: int, total_bytes: int | None
):
    if progress_callback:
        progress_callback(consumed_bytes, total_bytes)


def _invoke_cipher_callback(cipher_callback, content, discard=0):
    if cipher_callback:
        content = cipher_callback(content)
        return content[discard:]
    return content


class _IterableAdapter:
    def __init__(
        self,
        data: Iterable,
        progress_callback: Callable[[int, int | None], None] | None = None,
        crc_callback=None,
        cipher_callback=None,
    ):
        self.iter = iter(data)
        self.progress_callback = progress_callback
        self.offset = 0
        self.crc_callback = crc_callback
        self.cipher_callback = cipher_callback
        self.buffer = b""

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        _invoke_progress_callback(self.progress_callback, self.offset, None)

        content = next(self.iter)
        self.offset += len(content)

        _invoke_crc_callback(self.crc_callback, content)

        content = _invoke_cipher_callback(self.cipher_callback, content)

        return content

    @property
    def crc(self):
        if self.crc_callback:
            return self.crc_callback.crc
        elif has_crc_attr(self.iter):
            return self.iter.crc
        else:
            return None

    def read(self, amt: int | None = None):
        if amt is None:
            # 如果没有指定读取长度，读取所有剩余数据
            result = self.buffer
            self.buffer = b""
            for chunk in self:
                result += chunk
            return result

        while len(self.buffer) < amt:
            try:
                chunk = next(self)
                self.buffer += chunk
            except StopIteration:
                break

        result = self.buffer[:amt]
        self.buffer = self.buffer[amt:]
        return result


class _FileLikeAdapter:
    """通过这个适配器，可以给无法确定内容长度的 `fileobj` 加上进度监控。

    :param fileobj: file-like object，只要支持read即可
    :param progress_callback: 进度回调函数
    """

    def __init__(
        self,
        fileobj: SyncReadableBuffer,
        progress_callback: Callable[[int, int | None], None] | None = None,
        crc_callback=None,
        cipher_callback=None,
        discard=0,
    ):
        self.fileobj = fileobj
        self.progress_callback = progress_callback
        self.offset = 0

        self.crc_callback = crc_callback
        self.cipher_callback = cipher_callback
        self.discard = discard
        self.read_all = False

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        if self.read_all:
            raise StopIteration

        content = self.read(_CHUNK_SIZE)

        if content:
            return content
        else:
            raise StopIteration

    def read(self, amt: int | None = None):
        offset_start = self.offset
        if offset_start < self.discard and amt and self.cipher_callback:
            amt += self.discard

        content = self.fileobj.read(amt)
        if not content:
            self.read_all = True
            _invoke_progress_callback(self.progress_callback, self.offset, None)
        else:
            _invoke_progress_callback(self.progress_callback, self.offset, None)

            self.offset += len(content)

            real_discard = 0
            if offset_start < self.discard:
                if len(content) <= self.discard:
                    real_discard = len(content)
                else:
                    real_discard = self.discard

            _invoke_crc_callback(self.crc_callback, content, real_discard)
            content = _invoke_cipher_callback(self.cipher_callback, content, real_discard)

            self.discard -= real_discard
        return content

    @property
    def crc(self):
        if self.crc_callback:
            return self.crc_callback.crc
        elif has_crc_attr(self.fileobj):
            return self.fileobj.crc
        else:
            return None


class _BytesAndFileAdapter:
    """通过这个适配器，可以给 `data` 加上进度监控。

    :param data: 可以是unicode字符串（内部会转换为UTF-8编码的bytes）、bytes或file object
    :param progress_callback: 用户提供的进度报告回调，形如 callback(bytes_read, total_bytes)。
        其中bytes_read是已经读取的字节数；total_bytes是总的字节数。
    :param int size: `data` 包含的字节数。
    """

    def __init__(
        self,
        data: ObjectDataType,
        progress_callback: Callable[[int, int | None], None] | None = None,
        size: int | None = None,
        crc_callback=None,
        cipher_callback=None,
    ):
        self.data = to_bytes(data)
        self.progress_callback = progress_callback
        self.size = size
        self.offset = 0

        self.crc_callback = crc_callback
        self.cipher_callback = cipher_callback

    @property
    def len(self):
        return self.size

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        content = self.read(_CHUNK_SIZE)

        if content:
            return content
        else:
            raise StopIteration

    def read(self, amt: int | None = None):
        if self.size is None:
            raise ClientError("Bytes of file object adapter does not support discard bytes")

        if self.offset >= self.size:
            return to_bytes("")

        if amt is None or amt < 0:
            bytes_to_read = self.size - self.offset
        else:
            bytes_to_read = min(amt, self.size - self.offset)

        if isinstance(self.data, bytes):
            content = self.data[self.offset : self.offset + bytes_to_read]
        elif is_readable_buffer_sync(self.data):
            content = self.data.read(bytes_to_read)
        else:
            raise ClientError(f"{self.data.__class__.__name__} is not a file object")

        self.offset += bytes_to_read

        _invoke_progress_callback(self.progress_callback, min(self.offset, self.size), self.size)

        _invoke_crc_callback(self.crc_callback, content)

        content = _invoke_cipher_callback(self.cipher_callback, content)

        return content

    @property
    def crc(self):
        if self.crc_callback:
            return self.crc_callback.crc
        elif has_crc_attr(self.data):
            return self.data.crc
        else:
            return None


class Crc64:
    _POLY = 0x142F0E1EBA9EA3693
    _XOROUT = 0xFFFFFFFFFFFFFFFF

    def __init__(self, init_crc=0):
        self.crc64 = crcmod.Crc(self._POLY, initCrc=init_crc, rev=True, xorOut=self._XOROUT)
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
