import json
import logging
from pathlib import Path

from .. import utils
from .. import defaults
from ..http import Headers
from ..compat import stringify, to_unicode


logger = logging.getLogger(__name__)

_MAX_MULTIGET_PART_COUNT = 100000
_UPLOAD_TEMP_DIR = ".py-oss-upload"
_DOWNLOAD_TEMP_DIR = ".py-oss-download"


class _ResumableStoreBase:
    def __init__(self, root: Path | str, dir: Path | str):
        logger.debug(f"Init ResumableStoreBase, root path: {root}, temp dir: {dir}")
        self.dir = Path(root) / dir

        if self.dir.is_dir():
            return

        utils.makedir_p(self.dir)

    def get(self, key):
        pathname = self.__path(key)
        file = Path(pathname)

        logger.debug(f"ResumableStoreBase: get key: {key} from file path: {pathname}")

        if not file.exists():
            logger.debug(f"file {pathname} is not exist")
            return None

        try:
            with open(to_unicode(pathname), "r") as f:
                content = json.load(f)
        except ValueError:
            file.unlink()
            return None
        else:
            return stringify(content)

    def put(self, key, value):
        pathname = self.__path(key)

        with open(to_unicode(pathname), "w") as f:
            json.dump(value, f)

        logger.debug(f"ResumableStoreBase: put key: {key} to file path: {pathname}, value: {value}")

    def delete(self, key):
        pathname = self.__path(key)
        file = Path(pathname)
        file.unlink()

        logger.debug(f"ResumableStoreBase: delete key: {key}, file path: {pathname}")

    def __path(self, key: str) -> Path:
        return self.dir / key


def _normalize_path(path: str | Path) -> str:
    return str(Path(path).resolve())


class _PartToProcess:
    def __init__(self, part_number, start, end, part_crc=None):
        self.part_number = part_number
        self.start = start
        self.end = end
        self.part_crc = part_crc

    @property
    def size(self):
        return self.end - self.start

    def __hash__(self):
        return hash(self.__key)

    def __eq__(self, other):
        return self.__key == other.__key

    @property
    def __key(self):
        return self.part_number, self.start, self.end


def determine_part_size(total_size, preferred_size=None):
    """确定分片上传是分片的大小。

    :param int total_size: 总共需要上传的长度
    :param int preferred_size: 用户期望的分片大小。如果不指定则采用defaults.part_size

    :return: 分片大小
    """
    if not preferred_size:
        preferred_size = defaults.part_size

    return _determine_part_size_internal(total_size, preferred_size, defaults.max_part_count)


def _determine_part_size_internal(total_size, preferred_size, max_count):
    if total_size < preferred_size:
        return total_size

    while preferred_size * max_count < total_size or preferred_size < defaults.min_part_size:
        preferred_size = preferred_size * 2

    return preferred_size


def _split_to_parts(total_size, part_size):
    parts = []
    num_parts = utils.how_many(total_size, part_size)

    for i in range(num_parts):
        if i == num_parts - 1:
            start = i * part_size
            end = total_size
        else:
            start = i * part_size
            end = part_size + start

        parts.append(_PartToProcess(i + 1, start, end))

    return parts


def _populate_valid_headers(headers=None, valid_keys=None):
    """构建只包含有效keys的http header

    :param headers: 需要过滤的header
    :type headers: 可以是dict，建议是aliyun_oss_x.Headers

    :param valid_keys: 有效的关键key列表
    :type valid_keys: list

    :return: 只包含有效keys的http header, type: aliyun_oss_x.Headers
    """
    if headers is None or valid_keys is None:
        return None

    headers = Headers(headers)
    valid_headers = Headers()

    for key in valid_keys:
        if headers.get(key) is not None:
            valid_headers[key] = headers[key]

    if len(valid_headers) == 0:
        valid_headers = None

    return valid_headers


def _filter_invalid_headers(headers=None, invalid_keys=None):
    """过滤无效keys的http header

    :param headers: 需要过滤的header
    :type headers: 可以是dict，建议是aliyun_oss_x.Headers

    :param invalid_keys: 无效的关键key列表
    :type invalid_keys: list

    :return: 过滤无效header之后的http headers, type: aliyun_oss_x.Headers
    """
    if headers is None or invalid_keys is None:
        return None

    headers = Headers(headers)
    valid_headers = headers.copy()

    for key in invalid_keys:
        if valid_headers.get(key) is not None:
            valid_headers.pop(key)

    if len(valid_headers) == 0:
        valid_headers = None

    return valid_headers


def _populate_valid_params(params=None, valid_keys=None):
    """构建只包含有效keys的params

    :param params: 需要过滤的params
    :type params: dict

    :param valid_keys: 有效的关键key列表
    :type valid_keys: list

    :return: 只包含有效keys的params
    """
    if params is None or valid_keys is None:
        return None

    valid_params = dict()

    for key in valid_keys:
        if params.get(key) is not None:
            valid_params[key] = params[key]

    if len(valid_params) == 0:
        valid_params = None

    return valid_params


class _ObjectInfo:
    def __init__(self):
        self.size: int | None = None
        self.etag: str | None = None
        self.mtime: str | None = None

    @staticmethod
    def make(head_object_result):
        objectInfo = _ObjectInfo()
        objectInfo.size = head_object_result.content_length
        objectInfo.etag = head_object_result.etag
        objectInfo.mtime = head_object_result.last_modified

        return objectInfo
