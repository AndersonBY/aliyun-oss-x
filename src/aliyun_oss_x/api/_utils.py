from urllib.parse import quote, urlparse

from .. import utils


_ENDPOINT_TYPE_ALIYUN = 0
_ENDPOINT_TYPE_CNAME = 1
_ENDPOINT_TYPE_IP = 2
_ENDPOINT_TYPE_PATH_STYLE = 3


def _make_range_string(range):
    if range is None:
        return ""

    start = range[0]
    last = range[1]

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
    if utils.is_ip_or_localhost(netloc):
        return _ENDPOINT_TYPE_IP

    if is_cname:
        return _ENDPOINT_TYPE_CNAME

    if is_path_style:
        return _ENDPOINT_TYPE_PATH_STYLE

    if utils.is_valid_bucket_name(bucket_name):
        return _ENDPOINT_TYPE_ALIYUN
    else:
        return _ENDPOINT_TYPE_IP


class _UrlMaker:
    def __init__(self, endpoint, is_cname, is_path_style):
        p = urlparse(endpoint)

        self.scheme = p.scheme
        self.netloc = p.netloc
        self.is_cname = is_cname
        self.is_path_style = is_path_style

    def __call__(self, bucket_name, key, slash_safe=False):
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


def _normalize_endpoint(endpoint):
    url = endpoint

    if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
        url = "http://" + endpoint

    p = urlparse(url)

    if p.port is not None:
        return p.scheme + "://" + p.hostname + ":" + str(p.port)
    else:
        return p.scheme + "://" + p.hostname
