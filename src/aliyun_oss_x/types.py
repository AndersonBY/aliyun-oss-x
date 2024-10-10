import logging
import asyncio
from typing import Iterable, Protocol, Any, TypeGuard

from httpx import Response

_CHUNK_SIZE = 8 * 1024

logger = logging.getLogger(__name__)


class OSSResponse:
    def __init__(self, response: Response):
        self.response = response
        self.status = response.status_code
        self.headers = response.headers
        self.request_id = response.headers.get("x-oss-request-id", "")
        self._content_iter = response.iter_bytes()
        self._buffer = b""
        self.__all_read = False

        logger.debug(f"Get response headers, req-id:{self.request_id}, status: {self.status}, headers: {self.headers}")

    def read(self, amt: int | None = None):
        if self.__all_read:
            return b""

        if amt is None:
            content = b"".join([self._buffer] + list(self._content_iter))
            self._buffer = b""
            self.__all_read = True
            return content
        else:
            while len(self._buffer) < amt:
                try:
                    chunk = next(self._content_iter)
                    self._buffer += chunk
                except StopIteration:
                    self.__all_read = True
                    break

            result, self._buffer = self._buffer[:amt], self._buffer[amt:]
            return result

    def __iter__(self):
        return self.response.iter_bytes(_CHUNK_SIZE)


class AsyncOSSResponse:
    def __init__(self, response: Response):
        self.response = response
        self.status = response.status_code
        self.headers = response.headers
        self.request_id = response.headers.get("x-oss-request-id", "")
        self._content_iter = response.aiter_bytes()
        self._buffer = b""
        self.__all_read = False

        logger.debug(f"Get response headers, req-id:{self.request_id}, status: {self.status}, headers: {self.headers}")

    async def read(self, amt: int | None = None):
        if self.__all_read:
            return b""

        if amt is None:
            content = b"".join([self._buffer] + [chunk async for chunk in self._content_iter])
            self._buffer = b""
            self.__all_read = True
            return content
        else:
            while len(self._buffer) < amt:
                try:
                    chunk = await anext(self._content_iter)
                    self._buffer += chunk
                except StopAsyncIteration:
                    self.__all_read = True
                    break

            result, self._buffer = self._buffer[:amt], self._buffer[amt:]
            return result

    async def __aiter__(self):
        async for chunk in self.response.aiter_bytes(_CHUNK_SIZE):
            yield chunk


ResponseType = OSSResponse | AsyncOSSResponse


class SyncReadableBuffer(Protocol):
    def read(self, __size: int | None = None) -> bytes: ...


class AsyncReadableBuffer(Protocol):
    async def read(self, __size: int | None = None) -> bytes: ...


ReadableBuffer = SyncReadableBuffer | AsyncReadableBuffer

ObjectDataType = bytes | ReadableBuffer | Iterable


def is_readable_buffer(obj: Any) -> TypeGuard[ReadableBuffer]:
    return hasattr(obj, "read") and callable(obj.read)


def is_readable_buffer_sync(obj: Any) -> TypeGuard[SyncReadableBuffer]:
    return hasattr(obj, "read") and callable(obj.read) and not asyncio.iscoroutinefunction(obj.read)


def is_readable_buffer_async(obj: Any) -> TypeGuard[AsyncReadableBuffer]:
    return hasattr(obj, "read") and callable(obj.read) and asyncio.iscoroutinefunction(obj.read)


def has_crc_attr(obj: Any) -> TypeGuard[Any]:
    return hasattr(obj, "crc")
