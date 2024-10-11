import random
import string
import logging
import functools
import threading
from pathlib import Path
from typing import Callable, cast

from ..utils import (
    check_crc,
    http_date,
    md5_string,
    force_rename,
    silently_remove,
    SizedFileAdapter,
    b64encode_as_string,
    b64decode_from_string,
    copyfileobj_and_verify,
    calc_obj_crc_from_parts,
)
from .. import exceptions
from .. import defaults
from .. import http
from .. import models
from ..api import Bucket
from ..iterators import PartIterator
from ..crypto_bucket import CryptoBucket

from ..models import PartInfo
from ..task_queue import TaskQueue
from ..headers import (
    OSS_OBJECT_ACL,
    OSS_REQUEST_PAYER,
    OSS_TRAFFIC_LIMIT,
    IF_MATCH,
    IF_UNMODIFIED_SINCE,
    OSS_SERVER_SIDE_ENCRYPTION,
    OSS_SERVER_SIDE_DATA_ENCRYPTION,
)
from ._base import (
    _normalize_path,
    _ResumableStoreBase,
    _PartToProcess,
    _UPLOAD_TEMP_DIR,
    _DOWNLOAD_TEMP_DIR,
    _MAX_MULTIGET_PART_COUNT,
    _split_to_parts,
    _populate_valid_headers,
    _filter_invalid_headers,
    _populate_valid_params,
    determine_part_size,
    _determine_part_size_internal,
    _ObjectInfo,
)


logger = logging.getLogger(__name__)


def resumable_upload(
    bucket: Bucket | CryptoBucket,
    key: str,
    filename: str,
    store: "ResumableStore | None" = None,
    headers: dict | http.Headers | None = None,
    multipart_threshold: int | None = None,
    part_size: int | None = None,
    progress_callback: Callable[[int, int | None], None] | None = None,
    num_threads: int | None = None,
    params: dict | None = None,
):
    """断点上传本地文件。

    实现中采用分片上传方式上传本地文件，缺省的并发数是 `aliyun_oss_x.defaults.multipart_num_threads` ，并且在
    本地磁盘保存已经上传的分片信息。如果因为某种原因上传被中断，下次上传同样的文件，即源文件和目标文件路径都
    一样，就只会上传缺失的分片。

    缺省条件下，该函数会在用户 `HOME` 目录下保存断点续传的信息。当待上传的本地文件没有发生变化，
    且目标文件名没有变化时，会根据本地保存的信息，从断点开始上传。

    使用该函数应注意如下细节：
        #. 如果使用CryptoBucket，函数会退化为普通上传

    :param bucket: :class:`Bucket <aliyun_oss_x.Bucket>` 或者 ：:class:`CryptoBucket <aliyun_oss_x.CryptoBucket>` 对象
    :param key: 上传到用户空间的文件名
    :param filename: 待上传本地文件名
    :param store: 用来保存断点信息的持久存储，参见 :class:`ResumableStore` 的接口。如不指定，则使用 `ResumableStore` 。

    :param headers: HTTP头部
        # 调用外部函数put_object 或 init_multipart_upload传递完整headers
        # 调用外部函数uplpad_part目前只传递OSS_REQUEST_PAYER, OSS_TRAFFIC_LIMIT
        # 调用外部函数complete_multipart_upload目前只传递OSS_REQUEST_PAYER, OSS_OBJECT_ACL
    :type headers: 可以是dict，建议是aliyun_oss_x.Headers

    :param multipart_threshold: 文件长度大于该值时，则用分片上传。
    :param part_size: 指定分片上传的每个分片的大小。如不指定，则自动计算。
    :param progress_callback: 上传进度回调函数。参见 :ref:`progress_callback` 。
    :param num_threads: 并发上传的线程数，如不指定则使用 `aliyun_oss_x.defaults.multipart_num_threads` 。

    :param params: HTTP请求参数
        # 只有'sequential'这个参数才会被传递到外部函数init_multipart_upload中。
        # 其他参数视为无效参数不会往外部函数传递。
    :type params: dict
    """
    logger.debug(
        f"Start to resumable upload, bucket: {bucket.bucket_name}, key: {key}, filename: {filename}, headers: {headers}, "
        f"multipart_threshold: {multipart_threshold}, part_size: {part_size}, num_threads: {num_threads}"
    )
    size = Path(filename).stat().st_size
    multipart_threshold = defaults.get(multipart_threshold, defaults.multipart_threshold)

    logger.debug(f"The size of file to upload is: {size}, multipart_threshold: {multipart_threshold}")
    if size >= multipart_threshold:
        uploader = _ResumableUploader(
            bucket,
            key,
            filename,
            size,
            store,
            part_size=part_size,
            headers=headers,
            progress_callback=progress_callback,
            num_threads=num_threads,
            params=params,
        )
        result = uploader.upload()
    else:
        with Path(filename).open("rb") as f:
            result = bucket.put_object(key, f, headers=headers, progress_callback=progress_callback)

    return result


def resumable_download(
    bucket: Bucket | CryptoBucket,
    key: str,
    filename: str,
    multiget_threshold: int | None = None,
    part_size: int | None = None,
    progress_callback: Callable[[int, int | None], None] | None = None,
    num_threads: int | None = None,
    store: "ResumableDownloadStore | None" = None,
    params: dict | None = None,
    headers: dict | http.Headers | None = None,
):
    """断点下载。

    实现的方法是：
        #. 在本地创建一个临时文件，文件名由原始文件名加上一个随机的后缀组成；
        #. 通过指定请求的 `Range` 头按照范围并发读取OSS文件，并写入到临时文件里对应的位置；
        #. 全部完成之后，把临时文件重命名为目标文件 （即 `filename` ）

    在上述过程中，断点信息，即已经完成的范围，会保存在磁盘上。因为某种原因下载中断，后续如果下载
    同样的文件，也就是源文件和目标文件一样，就会先读取断点信息，然后只下载缺失的部分。

    缺省设置下，断点信息保存在 `HOME` 目录的一个子目录下。可以通过 `store` 参数更改保存位置。

    使用该函数应注意如下细节：
        #. 对同样的源文件、目标文件，避免多个程序（线程）同时调用该函数。因为断点信息会在磁盘上互相覆盖，或临时文件名会冲突。
        #. 避免使用太小的范围（分片），即 `part_size` 不宜过小，建议大于或等于 `aliyun_oss_x.defaults.multiget_part_size` 。
        #. 如果目标文件已经存在，那么该函数会覆盖此文件。
        #. 如果使用CryptoBucket，函数会退化为普通下载


    :param bucket: :class:`Bucket <aliyun_oss_x.Bucket>` 或者 ：:class:`CryptoBucket <aliyun_oss_x.CryptoBucket>` 对象
    :param str key: 待下载的远程文件名。
    :param str filename: 本地的目标文件名。
    :param int multiget_threshold: 文件长度大于该值时，则使用断点下载。
    :param int part_size: 指定期望的分片大小，即每个请求获得的字节数，实际的分片大小可能有所不同。
    :param progress_callback: 下载进度回调函数。参见 :ref:`progress_callback` 。
    :param num_threads: 并发下载的线程数，如不指定则使用 `aliyun_oss_x.defaults.multiget_num_threads` 。

    :param store: 用来保存断点信息的持久存储，可以指定断点信息所在的目录。
    :type store: `ResumableDownloadStore`

    :param dict params: 指定下载参数，可以传入versionId下载指定版本文件

    :param headers: HTTP头部,
        # 调用外部函数head_object目前只传递OSS_REQUEST_PAYER
        # 调用外部函数get_object_to_file, get_object目前需要向下传递的值有OSS_REQUEST_PAYER, OSS_TRAFFIC_LIMIT
    :type headers: 可以是dict，建议是aliyun_oss_x.Headers

    :raises: 如果OSS文件不存在，则抛出 :class:`NotFound <aliyun_oss_x.exceptions.NotFound>` ；也有可能抛出其他因下载文件而产生的异常。
    """
    logger.debug(
        f"Start to resumable download, bucket: {bucket.bucket_name}, key: {key}, filename: {filename}, multiget_threshold: {multiget_threshold}, "
        f"part_size: {part_size}, num_threads: {num_threads}"
    )
    multiget_threshold = defaults.get(multiget_threshold, defaults.multiget_threshold)

    valid_headers = _populate_valid_headers(headers, [OSS_REQUEST_PAYER, OSS_TRAFFIC_LIMIT])
    result = bucket.head_object(key, params=params, headers=valid_headers)
    logger.debug(
        f"The size of object to download is: {result.content_length}, multiget_threshold: {multiget_threshold}"
    )
    if result.content_length >= multiget_threshold:
        downloader = _ResumableDownloader(
            bucket,
            key,
            filename,
            _ObjectInfo.make(result),
            part_size=part_size,
            progress_callback=progress_callback,
            num_threads=num_threads,
            store=store,
            params=params,
            headers=valid_headers,
        )
        downloader.download(result.server_crc)
    else:
        bucket.get_object_to_file(
            key, filename, progress_callback=progress_callback, params=params, headers=valid_headers
        )


class _ResumableOperation:
    def __init__(
        self,
        bucket: Bucket | CryptoBucket,
        key: str,
        filename: str,
        size: int | None,
        store: "ResumableStore | ResumableDownloadStore",
        progress_callback: Callable[[int, int | None], None] | None = None,
        versionid: str | None = None,
    ):
        self.bucket = bucket
        self.key = key
        self.filename = filename
        self.size = size

        self._abspath = str(Path(filename).resolve())

        self.__store = store

        if versionid is None:
            self.__record_key = self.__store.make_store_key(bucket.bucket_name, self.key, self._abspath)
        else:
            self.__record_key = self.__store.make_store_key(bucket.bucket_name, self.key, self._abspath, versionid)

        logger.debug(f"Init _ResumableOperation, record_key: {self.__record_key}")

        # protect self.__progress_callback
        self.__plock = threading.Lock()
        self.__progress_callback = progress_callback

    def _del_record(self):
        self.__store.delete(self.__record_key)

    def _put_record(self, record):
        self.__store.put(self.__record_key, record)

    def _get_record(self):
        return self.__store.get(self.__record_key)

    def _report_progress(self, consumed_size):
        if self.__progress_callback:
            with self.__plock:
                self.__progress_callback(consumed_size, self.size)


class _ResumableDownloader(_ResumableOperation):
    def __init__(
        self,
        bucket: Bucket | CryptoBucket,
        key: str,
        filename: str,
        object_info: _ObjectInfo,
        part_size: int | None = None,
        store: "ResumableDownloadStore | None" = None,
        progress_callback: Callable[[int, int | None], None] | None = None,
        num_threads: int | None = None,
        params: dict | None = None,
        headers: dict | http.Headers | None = None,
    ):
        versionid = None
        if params is not None and params.get("versionId") is not None:
            versionid = params.get("versionId")
        super(_ResumableDownloader, self).__init__(
            bucket,
            key,
            filename,
            object_info.size,
            store or ResumableDownloadStore(),
            progress_callback=progress_callback,
            versionid=versionid,
        )
        self.objectInfo = object_info
        self.__op = "ResumableDownload"
        self.__part_size = defaults.get(part_size, defaults.multiget_part_size)
        self.__part_size = _determine_part_size_internal(self.size, self.__part_size, _MAX_MULTIGET_PART_COUNT)

        self.__tmp_file = None
        self.__num_threads = defaults.get(num_threads, defaults.multiget_num_threads)
        self.__finished_parts = None
        self.__finished_size = None
        self.__params = params
        self.__headers = headers

        # protect record
        self.__lock = threading.Lock()
        self.__record = None
        logger.debug(
            f"Init _ResumableDownloader, bucket: {bucket.bucket_name}, key: {key}, part_size: {self.__part_size}, num_thread: {self.__num_threads}"
        )

    def download(self, server_crc=None):
        self.__load_record()

        parts_to_download = self.__get_parts_to_download()
        logger.debug(f"Parts need to download: {parts_to_download}")

        # create tmp file if it is does not exist
        if self.__tmp_file is None:
            raise FileNotFoundError("tmp file not found")

        open(self.__tmp_file, "a").close()

        q = TaskQueue(
            functools.partial(self.__producer, parts_to_download=parts_to_download),
            [self.__consumer] * self.__num_threads,
        )
        q.run()

        if self.bucket.enable_crc and self.__finished_parts:
            parts = sorted(self.__finished_parts, key=lambda p: p.part_number)
            object_crc = calc_obj_crc_from_parts(parts)
            check_crc("resume download", object_crc, server_crc, None)

        force_rename(self.__tmp_file, self.filename)

        self._report_progress(self.size)
        self._del_record()

    def __producer(self, q, parts_to_download=None):
        if parts_to_download is None:
            return
        for part in parts_to_download:
            q.put(part)

    def __consumer(self, q):
        while q.ok():
            part = q.get()
            if part is None:
                break

            self.__download_part(part)

    def __download_part(self, part):
        self._report_progress(self.__finished_size)

        if self.__tmp_file is None:
            raise FileNotFoundError("tmp file not found")

        with open(self.__tmp_file, "rb+") as f:
            f.seek(part.start, 0)

            headers = _populate_valid_headers(self.__headers, [OSS_REQUEST_PAYER, OSS_TRAFFIC_LIMIT])
            if headers is None:
                headers = http.Headers()
            headers[IF_MATCH] = self.objectInfo.etag or ""
            headers[IF_UNMODIFIED_SINCE] = http_date(self.objectInfo.mtime)

            result = self.bucket.get_object(
                self.key, byte_range=(part.start, part.end - 1), headers=headers, params=self.__params
            )
            copyfileobj_and_verify(result, f, part.end - part.start, request_id=result.request_id)

        part.part_crc = result.client_crc
        logger.debug(
            f"down part success, add part info to record, part_number: {part.part_number}, start: {part.start}, end: {part.end}"
        )

        self.__finish_part(part)

    def __load_record(self):
        record = self._get_record()
        logger.debug(f"Load record return {record}")

        if record and not self.__is_record_sane(record):
            logger.warn("The content of record is invalid, delete the record")
            self._del_record()
            record = None

        if record and not Path(self.filename + record["tmp_suffix"]).exists():
            logger.warn(f"Temp file: {self.filename + record['tmp_suffix']} does not exist, delete the record")
            self._del_record()
            record = None

        if record and self.__is_remote_changed(record):
            logger.warn(f"Object: {self.key} has been overwritten，delete the record and tmp file")
            silently_remove(self.filename + record["tmp_suffix"])
            self._del_record()
            record = None

        if not record:
            record = {
                "op_type": self.__op,
                "bucket": self.bucket.bucket_name,
                "key": self.key,
                "size": self.objectInfo.size,
                "mtime": self.objectInfo.mtime,
                "etag": self.objectInfo.etag,
                "part_size": self.__part_size,
                "file_path": self._abspath,
                "tmp_suffix": self.__gen_tmp_suffix(),
                "parts": [],
            }
            logger.debug(
                f"Add new record, bucket: {self.bucket.bucket_name}, key: {self.key}, part_size: {self.__part_size}"
            )
            self._put_record(record)

        self.__tmp_file = self.filename + record["tmp_suffix"]
        self.__part_size = record["part_size"]
        self.__finished_parts = list(
            _PartToProcess(p["part_number"], p["start"], p["end"], p["part_crc"]) for p in record["parts"]
        )
        self.__finished_size = sum(p.size for p in self.__finished_parts)
        self.__record = record

    def __get_parts_to_download(self):
        assert self.__record

        if self.__finished_parts is None:
            return []

        all_set = set(_split_to_parts(self.size, self.__part_size))
        finished_set = set(self.__finished_parts)

        return sorted(list(all_set - finished_set), key=lambda p: p.part_number)

    def __is_record_sane(self, record):
        try:
            if record["op_type"] != self.__op:
                logger.error(f"op_type invalid, op_type in record:{record['op_type']} is invalid")
                return False

            for key in ("etag", "tmp_suffix", "file_path", "bucket", "key"):
                if not isinstance(record[key], str):
                    logger.error(f"{key} is not a string: {record[key]}")
                    return False

            for key in ("part_size", "size", "mtime"):
                if not isinstance(record[key], int):
                    logger.error(f"{key} is not an integer: {record[key]}")
                    return False

            if not isinstance(record["parts"], list):
                logger.error(f"parts is not a list: {record['parts']}")
                return False
        except KeyError as e:
            logger.error(f"Key not found: {e.args}")
            return False

        return True

    def __is_remote_changed(self, record):
        return (
            record["mtime"] != self.objectInfo.mtime
            or record["size"] != self.objectInfo.size
            or record["etag"] != self.objectInfo.etag
        )

    def __finish_part(self, part):
        with self.__lock:
            if self.__finished_parts is None:
                self.__finished_parts = []
            self.__finished_parts.append(part)
            self.__finished_size += part.size

            if self.__record is None:
                return

            self.__record["parts"].append(
                {"part_number": part.part_number, "start": part.start, "end": part.end, "part_crc": part.part_crc}
            )
            self._put_record(self.__record)

    def __gen_tmp_suffix(self):
        return ".tmp-" + "".join(random.choice(string.ascii_lowercase) for i in range(12))


class _ResumableUploader(_ResumableOperation):
    """以断点续传方式上传文件。

    :param bucket: :class:`Bucket <aliyun_oss_x.Bucket>` 对象
    :param key: 文件名
    :param filename: 待上传的文件名
    :param size: 文件总长度
    :param store: 用来保存进度的持久化存储
    :param headers: 传给 `init_multipart_upload` 的HTTP头部
    :param part_size: 分片大小。优先使用用户提供的值。如果用户没有指定，那么对于新上传，计算出一个合理值；对于老的上传，采用第一个
        分片的大小。
    :param progress_callback: 上传进度回调函数。参见 :ref:`progress_callback` 。
    """

    def __init__(
        self,
        bucket: Bucket | CryptoBucket,
        key: str,
        filename: str,
        size: int,
        store: "ResumableStore | None" = None,
        headers: dict | http.Headers | None = None,
        part_size: int | None = None,
        progress_callback: Callable[[int, int | None], None] | None = None,
        num_threads: int | None = None,
        params: dict | None = None,
    ):
        super(_ResumableUploader, self).__init__(
            bucket, key, filename, size, store or ResumableStore(), progress_callback=progress_callback
        )

        self.__op = "ResumableUpload"
        self.__headers = headers

        self.__part_size = defaults.get(part_size, defaults.part_size)

        self.__mtime = Path(filename).stat().st_mtime

        self.__num_threads = defaults.get(num_threads, defaults.multipart_num_threads)

        self.__upload_id: str = ""

        self.__params = params

        # protect below fields
        self.__lock = threading.Lock()
        self.__record = None
        self.__finished_size = 0
        self.__finished_parts: list[PartInfo] = []
        self.__encryption = False
        self.__record_upload_context = False
        self.__upload_context = None

        if isinstance(self.bucket, CryptoBucket):
            self.__encryption = True
            self.__record_upload_context = True

        logger.debug(
            f"Init _ResumableUploader, bucket: {bucket.bucket_name}, key: {key}, part_size: {self.__part_size}, num_thread: {self.__num_threads}"
        )

    def upload(self):
        self.__load_record()

        parts_to_upload = self.__get_parts_to_upload(self.__finished_parts)
        parts_to_upload = sorted(parts_to_upload, key=lambda p: p.part_number)
        logger.debug(f"Parts need to upload: {parts_to_upload}")

        q = TaskQueue(
            functools.partial(self.__producer, parts_to_upload=parts_to_upload), [self.__consumer] * self.__num_threads
        )
        q.run()

        self._report_progress(self.size)

        headers = _populate_valid_headers(self.__headers, [OSS_REQUEST_PAYER, OSS_OBJECT_ACL])
        result = self.bucket.complete_multipart_upload(
            self.key, self.__upload_id, self.__finished_parts, headers=headers
        )
        self._del_record()

        return result

    def __producer(self, q, parts_to_upload=None):
        if parts_to_upload is None:
            return
        for part in parts_to_upload:
            q.put(part)

    def __consumer(self, q):
        while True:
            part = q.get()
            if part is None:
                break

            self.__upload_part(part)

    def __upload_part(self, part):
        with Path(self.filename).open("rb") as f:
            self._report_progress(self.__finished_size)

            f.seek(part.start, 0)
            headers = _populate_valid_headers(self.__headers, [OSS_REQUEST_PAYER, OSS_TRAFFIC_LIMIT])
            if self.__encryption:
                result = cast(CryptoBucket, self.bucket).upload_part(
                    self.key,
                    self.__upload_id,
                    part.part_number,
                    SizedFileAdapter(f, part.size),
                    headers=headers,
                    upload_context=self.__upload_context,
                )
            else:
                result = self.bucket.upload_part(
                    self.key, self.__upload_id, part.part_number, SizedFileAdapter(f, part.size), headers=headers
                )

            logger.debug(
                f"Upload part success, add part info to record, part_number: {part.part_number}, etag: {result.etag}, size: {part.size}"
            )
            self.__finish_part(PartInfo(part.part_number, result.etag, size=part.size, part_crc=result.crc))

    def __finish_part(self, part_info: PartInfo):
        with self.__lock:
            self.__finished_parts.append(part_info)
            self.__finished_size += part_info.size or 0

    def __load_record(self):
        record = self._get_record()
        logger.debug(f"Load record return {record}")

        if record and not self.__is_record_sane(record):
            logger.warn("The content of record is invalid, delete the record")
            self._del_record()
            record = None

        if record and self.__file_changed(record):
            logger.warn(f"File: {self.filename} has been changed, delete the record")
            self._del_record()
            record = None

        if record and not self.__upload_exists(record["upload_id"]):
            logger.warn(f"Multipart upload: {record['upload_id']} does not exist, delete the record")
            self._del_record()
            record = None

        if not record:
            params = _populate_valid_params(self.__params, [Bucket.SEQUENTIAL])
            part_size = determine_part_size(self.size, self.__part_size)
            logger.debug(
                "Upload File size: {0}, User-specify part_size: {1}, Calculated part_size: {2}".format(
                    self.size, self.__part_size, part_size
                )
            )
            material_record = None
            if self.__encryption:
                upload_context = models.MultipartUploadCryptoContext(self.size, part_size)
                upload_id = (
                    cast(CryptoBucket, self.bucket)
                    .init_multipart_upload(self.key, self.__headers, params, upload_context)
                    .upload_id
                )
                if self.__record_upload_context and upload_context.content_crypto_material:
                    material = upload_context.content_crypto_material
                    material_record = {
                        "wrap_alg": material.wrap_alg,
                        "cek_alg": material.cek_alg,
                        "encrypted_key": b64encode_as_string(material.encrypted_key),
                        "encrypted_iv": b64encode_as_string(material.encrypted_iv),
                        "mat_desc": material.mat_desc,
                    }
            else:
                upload_id = self.bucket.init_multipart_upload(self.key, self.__headers, params).upload_id

            record = {
                "op_type": self.__op,
                "upload_id": upload_id,
                "file_path": self._abspath,
                "size": self.size,
                "mtime": self.__mtime,
                "bucket": self.bucket.bucket_name,
                "key": self.key,
                "part_size": part_size,
            }

            if self.__record_upload_context:
                record["content_crypto_material"] = material_record

            logger.debug(
                f"Add new record, bucket: {self.bucket.bucket_name}, key: {self.key}, upload_id: {upload_id}, part_size: {part_size}"
            )

            self._put_record(record)

        self.__record = record
        self.__part_size = self.__record["part_size"]
        self.__upload_id: str = self.__record["upload_id"]
        if self.__record_upload_context:
            if "content_crypto_material" in self.__record:
                material_record = self.__record["content_crypto_material"]
                wrap_alg = material_record["wrap_alg"]
                cek_alg = material_record["cek_alg"]
                if (
                    cek_alg != cast(CryptoBucket, self.bucket).crypto_provider.cipher.alg
                    or wrap_alg != cast(CryptoBucket, self.bucket).crypto_provider.wrap_alg
                ):
                    err_msg = "Envelope or data encryption/decryption algorithm is inconsistent"
                    raise exceptions.InconsistentError(err_msg)
                content_crypto_material = models.ContentCryptoMaterial(
                    cast(CryptoBucket, self.bucket).crypto_provider.cipher,
                    material_record["wrap_alg"],
                    b64decode_from_string(material_record["encrypted_key"]),
                    b64decode_from_string(material_record["encrypted_iv"]),
                    material_record["mat_desc"],
                )
                self.__upload_context = models.MultipartUploadCryptoContext(
                    self.size, self.__part_size, content_crypto_material
                )

            else:
                err_msg = "If record_upload_context flag is true, content_crypto_material must in the the record"
                raise exceptions.InconsistentError(err_msg)

        else:
            if "content_crypto_material" in self.__record:
                err_msg = "content_crypto_material must in the the record, but record_upload_context flat is false"
                raise exceptions.InvalidEncryptionRequest(err_msg)

        self.__finished_parts = self.__get_finished_parts()
        self.__finished_size = sum(p.size or 0 for p in self.__finished_parts)

    def __get_finished_parts(self) -> list[PartInfo]:
        parts = []

        valid_headers = _filter_invalid_headers(
            self.__headers, [OSS_SERVER_SIDE_ENCRYPTION, OSS_SERVER_SIDE_DATA_ENCRYPTION]
        )

        for part in PartIterator(self.bucket, self.key, self.__upload_id, headers=valid_headers):
            parts.append(part)

        return parts

    def __upload_exists(self, upload_id):
        try:
            valid_headers = _filter_invalid_headers(
                self.__headers, [OSS_SERVER_SIDE_ENCRYPTION, OSS_SERVER_SIDE_DATA_ENCRYPTION]
            )
            list(PartIterator(self.bucket, self.key, upload_id, "0", max_parts=1, headers=valid_headers))
        except exceptions.NoSuchUpload:
            return False
        else:
            return True

    def __file_changed(self, record):
        return record["mtime"] != self.__mtime or record["size"] != self.size

    def __get_parts_to_upload(self, parts_uploaded):
        all_parts = _split_to_parts(self.size, self.__part_size)
        if not parts_uploaded:
            return all_parts

        all_parts_map = dict((p.part_number, p) for p in all_parts)

        for uploaded in parts_uploaded:
            if uploaded.part_number in all_parts_map:
                del all_parts_map[uploaded.part_number]

        return all_parts_map.values()

    def __is_record_sane(self, record):
        try:
            if record["op_type"] != self.__op:
                logger.error(f"op_type invalid, op_type in record: {record['op_type']} is invalid")
                return False

            for key in ("upload_id", "file_path", "bucket", "key"):
                if not isinstance(record[key], str):
                    logger.error(f"Type Error, {key} in record is not a string type: {record[key]}")
                    return False

            for key in ("size", "part_size"):
                if not isinstance(record[key], int):
                    logger.error(f"Type Error, {key} in record is not an integer type: {record[key]}")
                    return False

            if not isinstance(record["mtime"], int) and not isinstance(record["mtime"], float):
                logger.error(f"Type Error, mtime in record is not a float or an integer type: {record['mtime']}")
                return False

        except KeyError as e:
            logger.error(f"Key not found: {e.args}")
            return False

        return True


class ResumableStore(_ResumableStoreBase):
    """保存断点上传断点信息的类。

    每次上传的信息会保存在 `root/dir/` 下面的某个文件里。

    :param str root: 父目录，缺省为HOME
    :param str dir: 子目录，缺省为 `_UPLOAD_TEMP_DIR`
    """

    def __init__(self, root: Path | str | None = None, dir: Path | str | None = None):
        super(ResumableStore, self).__init__(Path(root or Path.home()), Path(dir or _UPLOAD_TEMP_DIR))

    @staticmethod
    def make_store_key(bucket_name: str, key: str, filename: str, version_id: str | None = None) -> str:
        filepath = _normalize_path(filename)

        oss_pathname = f"oss://{bucket_name}/{key}"
        return md5_string(oss_pathname) + "--" + md5_string(filepath)


class ResumableDownloadStore(_ResumableStoreBase):
    """保存断点下载断点信息的类。

    每次下载的断点信息会保存在 `root/dir/` 下面的某个文件里。

    :param str root: 父目录，缺省为HOME
    :param str dir: 子目录，缺省为 `_DOWNLOAD_TEMP_DIR`
    """

    def __init__(self, root: Path | str | None = None, dir: Path | str | None = None):
        super(ResumableDownloadStore, self).__init__(Path(root or Path.home()), Path(dir or _DOWNLOAD_TEMP_DIR))

    @staticmethod
    def make_store_key(bucket_name: str, key: str, filename: str, version_id: str | None = None) -> str:
        filepath = _normalize_path(filename)

        if version_id is None:
            oss_pathname = f"oss://{bucket_name}/{key}"
        else:
            oss_pathname = f"oss://{bucket_name}/{key}?versionid={version_id}"
        return md5_string(oss_pathname) + "--" + md5_string(filepath)


def make_upload_store(root: Path | str | None = None, dir: Path | str | None = None):
    return ResumableStore(root=root, dir=dir)


def make_download_store(root: Path | str | None = None, dir: Path | str | None = None):
    return ResumableDownloadStore(root=root, dir=dir)
