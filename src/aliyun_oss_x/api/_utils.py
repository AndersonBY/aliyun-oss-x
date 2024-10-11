from typing import Optional, Sequence
from urllib.parse import quote, urlparse

from ..utils import is_ip_or_localhost, is_valid_bucket_name


_ENDPOINT_TYPE_ALIYUN = 0
_ENDPOINT_TYPE_CNAME = 1
_ENDPOINT_TYPE_IP = 2
_ENDPOINT_TYPE_PATH_STYLE = 3


def _make_range_string(range: Optional[Sequence[Optional[int]]]) -> str:
    if range is None:
        return ""

    if len(range) != 2:
        raise ValueError("range 必须包含两个元素")

    start, last = range

    if start is None and last is None:
        return ""

    return "bytes=" + _range(start, last)


def _range(start, last):
    def to_str(pos):
        if pos is None:
            return ""
        else:
            return str(pos)

    return to_str(start) + "-" + to_str(last)


def _determine_endpoint_type(netloc, is_cname, bucket_name, is_path_style):
    if is_ip_or_localhost(netloc):
        return _ENDPOINT_TYPE_IP

    if is_cname:
        return _ENDPOINT_TYPE_CNAME

    if is_path_style:
        return _ENDPOINT_TYPE_PATH_STYLE

    if is_valid_bucket_name(bucket_name):
        return _ENDPOINT_TYPE_ALIYUN
    else:
        return _ENDPOINT_TYPE_IP


class _UrlMaker:
    def __init__(self, endpoint: str, is_cname: bool, is_path_style: bool):
        p = urlparse(endpoint)

        self.scheme = p.scheme
        self.netloc = p.netloc
        self.is_cname = is_cname
        self.is_path_style = is_path_style

    def __call__(self, bucket_name: str, key: str, slash_safe: bool = False) -> str:
        self.type = _determine_endpoint_type(self.netloc, self.is_cname, bucket_name, self.is_path_style)

        safe = "/" if slash_safe is True else ""
        key = quote(key, safe=safe)

        if self.type == _ENDPOINT_TYPE_CNAME:
            return f"{self.scheme}://{self.netloc}/{key}"

        if self.type == _ENDPOINT_TYPE_IP or self.type == _ENDPOINT_TYPE_PATH_STYLE:
            if bucket_name:
                return f"{self.scheme}://{self.netloc}/{bucket_name}/{key}"
            else:
                return f"{self.scheme}://{self.netloc}/{key}"

        if not bucket_name:
            assert not key
            return f"{self.scheme}://{self.netloc}"

        return f"{self.scheme}://{bucket_name}.{self.netloc}/{key}"


def _normalize_endpoint(endpoint: str):
    url = endpoint

    if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
        url = "http://" + endpoint

    p = urlparse(url)

    if p.port is not None:
        return p.scheme + "://" + (p.hostname or "") + ":" + str(p.port)
    else:
        return p.scheme + "://" + (p.hostname or "")
