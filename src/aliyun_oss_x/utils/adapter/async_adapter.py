import os.path
import logging
from typing import Callable, Union, AsyncIterable, Iterable, AsyncIterator, Awaitable

from ...compat import to_bytes
from ...exceptions import ClientError
from ...types import (
    ReadableBuffer,
    ObjectDataType,
    is_readable_buffer,
    is_readable_buffer_async,
    is_readable_buffer_sync,
    has_crc_attr,
)
from .. import Crc64


logger = logging.getLogger(__name__)


class AsyncSizedFileAdapter:
    """通过这个适配器（Adapter），可以把原先的 `file_object` 的长度限制到等于 `size`。"""

    def __init__(self, file_object: ReadableBuffer, size: int):
        self.file_object = file_object
        self.size = size
        self.offset = 0

    async def read(self, amt=None):
        if self.offset >= self.size:
            return b""

        if (amt is None or amt < 0) or (amt + self.offset >= self.size):
            _data = self.file_object.read(self.size - self.offset)
            if isinstance(_data, Awaitable):
                data = await _data
            else:
                data = _data
            self.offset = self.size
            return data

        self.offset += amt
        _data = self.file_object.read(amt)
        if isinstance(_data, Awaitable):
            return await _data
        else:
            return _data

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

AsyncAdapterType = Union["_AsyncBytesAndFileAdapter", "_AsyncIterableAdapter", "_AsyncFileLikeAdapter"]
IterableType = Union[AsyncIterable, Iterable]


def make_progress_adapter_async(
    data: AsyncAdapterType | ObjectDataType, progress_callback: Callable[[int, int | None], None] | None, size=None
):
    """异步版本的 make_progress_adapter，用于 AsyncClient 的 data 参数。"""

    data = to_bytes(data)

    if size is None:
        size = _get_data_size(data)

    if not size:
        if is_readable_buffer(data):
            return _AsyncFileLikeAdapter(data, progress_callback)
        elif isinstance(data, IterableType):
            return _AsyncIterableAdapter(data, progress_callback)
        else:
            raise ClientError(f"{data.__class__.__name__} is not a file object, nor an iterator")
    else:
        return _AsyncBytesAndFileAdapter(data, progress_callback, size)


def make_crc_adapter_async(data: AsyncAdapterType | ObjectDataType, init_crc=0, discard=0):
    """异步版本的 make_crc_adapter，用于 AsyncClient 的 data 参数。"""

    data = to_bytes(data)

    if _has_data_size_attr(data):
        if discard:
            raise ClientError("Bytes or file object adapter does not support discard bytes")
        return _AsyncBytesAndFileAdapter(data, size=_get_data_size(data), crc_callback=Crc64(init_crc))
    elif is_readable_buffer(data):
        return _AsyncFileLikeAdapter(data, crc_callback=Crc64(init_crc), discard=discard)
    elif isinstance(data, IterableType):
        if discard:
            raise ClientError("Iterator adapter does not support discard bytes")
        return _AsyncIterableAdapter(data, crc_callback=Crc64(init_crc))
    else:
        raise ClientError(f"{data.__class__.__name__} is not a file object, nor an iterator")


def make_cipher_adapter_async(data: ObjectDataType, cipher_callback: Callable[[bytes], bytes], discard: int = 0):
    """异步版本的 make_cipher_adapter，用于 AsyncClient 的 data 参数。"""

    data = to_bytes(data)

    if _has_data_size_attr(data):
        if discard:
            raise ClientError("Bytes or file object adapter does not support discard bytes")
        return _AsyncBytesAndFileAdapter(data, size=_get_data_size(data), cipher_callback=cipher_callback)
    if is_readable_buffer(data):
        return _AsyncFileLikeAdapter(data, cipher_callback=cipher_callback, discard=discard)
    elif isinstance(data, IterableType):
        if discard:
            raise ClientError("Iterator adapter does not support discard bytes")
        return _AsyncIterableAdapter(data, cipher_callback=cipher_callback)
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


class _AsyncIterableAdapter:
    def __init__(
        self,
        data: IterableType,
        progress_callback: Callable[[int, int | None], None] | None = None,
        crc_callback=None,
        cipher_callback=None,
    ):
        self.iter = data.__aiter__() if isinstance(data, AsyncIterable) else iter(data)
        self.progress_callback = progress_callback
        self.offset = 0
        self.crc_callback = crc_callback
        self.cipher_callback = cipher_callback
        self.buffer = b""

    def __aiter__(self):
        return self

    async def __anext__(self):
        await self._report_progress()
        try:
            if isinstance(self.iter, AsyncIterator):
                content = await self.iter.__anext__()
            else:
                content = next(self.iter)
        except StopIteration:
            raise StopAsyncIteration

        if isinstance(content, bytes):
            length = len(content)
        else:
            length = len(to_bytes(content))
        self.offset += length

        _invoke_crc_callback(self.crc_callback, content)

        content = _invoke_cipher_callback(self.cipher_callback, content)

        return content

    async def _report_progress(self):
        _invoke_progress_callback(self.progress_callback, self.offset, None)

    @property
    def crc(self):
        if self.crc_callback:
            return self.crc_callback.crc
        elif has_crc_attr(self.iter):
            return self.iter.crc
        else:
            return None

    async def read(self, amt: int | None = None):
        if amt is None:
            # 如果没有指定读取长度,读取所有剩余数据
            result = self.buffer
            self.buffer = b""
            async for chunk in self:
                result += chunk
            return result

        while len(self.buffer) < amt:
            try:
                chunk = await self.__anext__()
                self.buffer += chunk
            except StopAsyncIteration:
                break

        result = self.buffer[:amt]
        self.buffer = self.buffer[amt:]
        return result


class _AsyncFileLikeAdapter:
    """通过这个适配器，可以给无法确定内容长度的 `fileobj` 加上进度监控。"""

    def __init__(
        self,
        fileobj: ReadableBuffer,
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

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.read_all:
            raise StopAsyncIteration

        content = await self.read(_CHUNK_SIZE)

        if content:
            return content
        else:
            raise StopAsyncIteration

    async def read(self, amt: int | None = 0):
        offset_start = self.offset
        if offset_start < self.discard and amt and self.cipher_callback:
            amt += self.discard

        _content = self.fileobj.read(amt)
        if isinstance(_content, Awaitable):
            content = await _content
        else:
            content = _content

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


class _AsyncBytesAndFileAdapter:
    """通过这个适配器，可以给 `data` 加上进度监控。"""

    def __init__(
        self,
        data: AsyncAdapterType | ObjectDataType,
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

    def __aiter__(self):
        return self

    async def __anext__(self):
        content = await self.read(_CHUNK_SIZE)

        if content:
            return content
        else:
            raise StopAsyncIteration

    async def read(self, amt: int | None = 0):
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
        elif is_readable_buffer_async(self.data):
            content = await self.data.read(bytes_to_read)
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
