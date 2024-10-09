import logging

from httpx import Response

_CHUNK_SIZE = 8 * 1024

logger = logging.getLogger(__name__)


class OSSResponse:
    def __init__(self, response: Response):
        self.response = response
        self.status = response.status_code
        self.headers = response.headers
        self.request_id = response.headers.get("x-oss-request-id", "")
        self.response.read()

        # When a response contains no body, iter_content() cannot
        # be run twice (requests.exceptions.StreamConsumedError will be raised).
        # For details of the issue, please see issue #82
        #
        # To work around this issue, we simply return b'' when everything has been read.
        #
        # Note you cannot use self.response.raw.read() to implement self.read(), because
        # raw.read() does not uncompress response body when the encoding is gzip etc., and
        # we try to avoid depends on details of self.response.raw.
        self.__all_read = False

        logger.debug(f"Get response headers, req-id:{self.request_id}, status: {self.status}, headers: {self.headers}")

    def read(self, amt=None):
        if self.__all_read:
            return b""

        if amt is None:
            content = self.response.read()
            self.__all_read = True
            return content
        else:
            content = self.response.read()
            if not content:
                self.__all_read = True
            return content

    def __iter__(self):
        return self.response.iter_bytes(_CHUNK_SIZE)
