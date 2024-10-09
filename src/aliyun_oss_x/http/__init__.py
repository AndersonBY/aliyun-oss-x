import logging
import platform

import httpx
from httpx import Headers

from ..compat import to_bytes
from ..types import OSSResponse
from ..__version__ import __version__
from ..exceptions import RequestError
from ..utils import file_object_remaining_bytes, SizedFileAdapter


USER_AGENT = f"aliyun-sdk-python-light/{__version__}({platform.system()}/{platform.release()}/{platform.machine()};{platform.python_version()})"

logger = logging.getLogger(__name__)


class Session:
    """属于同一个 Session 的请求共享一组连接池，如有可能也会重用HTTP连接。"""

    def __init__(self, proxies: dict | None = None, http2: bool = True):
        self.proxies = proxies
        self.http2 = http2
        self.client = httpx.Client(http2=http2, proxies=proxies)

    def do_request(self, req: "Request", timeout: float):
        try:
            logger.debug(
                f"发送请求,方法: {req.method}, URL: {req.url}, 参数: {req.params}, 头部: {req.headers}, 超时: {timeout}, 代理: {req.proxies}"
            )

            if req.proxies:
                self.client = httpx.Client(http2=self.http2, proxies=req.proxies)

            response = self.client.request(
                method=req.method,
                url=req.url,
                data=req.data,
                params=req.params,
                headers=req.headers,
                timeout=timeout,
            )
            return OSSResponse(response)
        except httpx.RequestError as e:
            raise RequestError(e)


class Request:
    def __init__(
        self,
        method,
        url,
        data=None,
        params=None,
        headers=None,
        app_name="",
        proxies=None,
        region=None,
        product=None,
        cloudbox_id=None,
    ):
        self.method = method
        self.url = url
        self.data = data
        self.params = params or {}
        self.proxies = proxies
        self.region = region
        self.product = product
        self.cloudbox_id = cloudbox_id

        if not isinstance(headers, Headers):
            self.headers = Headers(headers or {})
        else:
            self.headers = headers

        if "User-Agent" not in self.headers:
            if app_name:
                self.headers["User-Agent"] = USER_AGENT + "/" + app_name
            else:
                self.headers["User-Agent"] = USER_AGENT

        logger.debug(f"Init request, method: {method}, url: {url}, params: {params}, headers: {headers}")


class AsyncSession:
    """属于同一个异步 Session 的请求共享一组连接池,如有可能也会重用HTTP连接。"""

    def __init__(self, proxies: dict | None = None, http2: bool = True):
        self.default_proxies = proxies
        self.http2 = http2
        self.client = httpx.AsyncClient(http2=http2, proxies=proxies)

    async def do_request(self, req: "AsyncRequest", timeout: float):
        try:
            logger.debug(
                f"发送异步请求,方法: {req.method}, URL: {req.url}, 参数: {req.params}, 头部: {req.headers}, 超时: {timeout}, 代理: {req.proxies}"
            )

            if req.proxies and req.proxies != self.default_proxies:
                async with httpx.AsyncClient(http2=self.http2, proxies=req.proxies) as client:
                    response = await client.request(
                        method=req.method,
                        url=req.url,
                        data=req.data,
                        params=req.params,
                        headers=req.headers,
                        timeout=timeout,
                    )
            else:
                response = await self.client.request(
                    method=req.method,
                    url=req.url,
                    data=req.data,
                    params=req.params,
                    headers=req.headers,
                    timeout=timeout,
                )

            return OSSResponse(response)
        except httpx.RequestError as e:
            raise RequestError(e)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()


class AsyncRequest:
    def __init__(
        self,
        method,
        url,
        data=None,
        params=None,
        headers=None,
        app_name="",
        proxies=None,
        region=None,
        product=None,
        cloudbox_id=None,
    ):
        self.method = method
        self.url = url
        self.data = data
        self.params = params or {}
        self.proxies = proxies
        self.region = region
        self.product = product
        self.cloudbox_id = cloudbox_id

        if not isinstance(headers, Headers):
            self.headers = Headers(headers or {})
        else:
            self.headers = headers

        if "User-Agent" not in self.headers:
            if app_name:
                self.headers["User-Agent"] = USER_AGENT + "/" + app_name
            else:
                self.headers["User-Agent"] = USER_AGENT

        logger.debug(f"初始化异步请求, 方法: {method}, URL: {url}, 参数: {params}, 头部: {headers}")


# requests对于具有fileno()方法的file object，会用fileno()的返回值作为Content-Length。
# 这对于已经读取了部分内容，或执行了seek()的file object是不正确的。
#
# _convert_request_body()对于支持seek()和tell() file object，确保是从
# 当前位置读取，且只读取当前位置到文件结束的内容。
def _convert_request_body(data):
    data = to_bytes(data)

    if hasattr(data, "__len__"):
        return data

    if hasattr(data, "seek") and hasattr(data, "tell"):
        return SizedFileAdapter(data, file_object_remaining_bytes(data))

    return data
