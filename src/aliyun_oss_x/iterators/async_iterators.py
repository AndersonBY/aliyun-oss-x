from typing import List, Any, Tuple, AsyncIterator, TypeVar, Generic

from httpx import Headers

from .. import defaults
from ..exceptions import ServerError
from ..api import AsyncService, AsyncBucket
from ..models import MultipartUploadInfo, SimplifiedObjectInfo, SimplifiedBucketInfo, PartInfo


T = TypeVar("T")


class _BaseIterator(Generic[T]):
    def __init__(self, marker: str, max_retries: int | None):
        self.is_truncated = True
        self.next_marker = marker

        max_retries = defaults.get(max_retries, defaults.request_retries)
        self.max_retries = max_retries if max_retries > 0 else 1

        self.entries: List[Any] = []

    async def _fetch(self) -> Tuple[bool, str]:
        raise NotImplementedError

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    async def __anext__(self) -> T:
        while True:
            if self.entries:
                return self.entries.pop(0)

            if not self.is_truncated:
                raise StopAsyncIteration

            await self.fetch_with_retry()

    async def fetch_with_retry(self):
        for i in range(self.max_retries):
            try:
                self.is_truncated, self.next_marker = await self._fetch()
            except ServerError as e:
                if e.status // 100 != 5:
                    raise

                if i == self.max_retries - 1:
                    raise
            else:
                return


class AsyncBucketIterator(_BaseIterator[SimplifiedBucketInfo]):
    """遍历用户Bucket的迭代器。

    每次迭代返回的是 :class:`SimplifiedBucketInfo <oss2.models.SimplifiedBucketInfo>` 对象。

    :param service: :class:`Service <oss2.Service>` 对象
    :param prefix: 只列举匹配该前缀的Bucket
    :param marker: 分页符。只列举Bucket名字典序在此之后的Bucket
    :param max_keys: 每次调用 `list_buckets` 时的max_keys参数。注意迭代器返回的数目可能会大于该值。
    """

    def __init__(
        self,
        service: AsyncService,
        prefix: str = "",
        marker: str = "",
        max_keys: int = 100,
        max_retries: int | None = None,
    ):
        super(AsyncBucketIterator, self).__init__(marker, max_retries)
        self.service = service
        self.prefix = prefix
        self.max_keys = max_keys

    async def _fetch(self):
        result = await self.service.list_buckets(prefix=self.prefix, marker=self.next_marker, max_keys=self.max_keys)
        self.entries = result.buckets

        return result.is_truncated, result.next_marker


class AsyncObjectIterator(_BaseIterator[SimplifiedObjectInfo]):
    """遍历Bucket里文件的迭代器。

    每次迭代返回的是 :class:`SimplifiedObjectInfo <oss2.models.SimplifiedObjectInfo>` 对象。
    当 `SimplifiedObjectInfo.is_prefix()` 返回True时，表明是公共前缀（目录）。

    :param bucket: :class:`Bucket <oss2.Bucket>` 对象
    :param prefix: 只列举匹配该前缀的文件
    :param delimiter: 目录分隔符
    :param marker: 分页符
    :param max_keys: 每次调用 `list_objects` 时的max_keys参数。注意迭代器返回的数目可能会大于该值。

    :param headers: HTTP头部
    :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict
    """

    def __init__(
        self,
        bucket: AsyncBucket,
        prefix: str = "",
        delimiter: str = "",
        marker: str = "",
        max_keys: int = 100,
        max_retries: int | None = None,
        headers: Headers | None = None,
    ):
        super(AsyncObjectIterator, self).__init__(marker, max_retries)

        self.bucket = bucket
        self.prefix = prefix
        self.delimiter = delimiter
        self.max_keys = max_keys
        self.headers = Headers(headers)

    async def _fetch(self):
        result = await self.bucket.list_objects(
            prefix=self.prefix,
            delimiter=self.delimiter,
            marker=self.next_marker,
            max_keys=self.max_keys,
            headers=self.headers,
        )
        self.entries = result.object_list + [
            SimplifiedObjectInfo(prefix, 0, "", "", 0, "") for prefix in result.prefix_list
        ]
        self.entries.sort(key=lambda obj: obj.key)

        return result.is_truncated, result.next_marker


class AsyncObjectIteratorV2(_BaseIterator[SimplifiedObjectInfo]):
    """遍历Bucket里文件的迭代器。

    每次迭代返回的是 :class:`SimplifiedObjectInfo <oss2.models.SimplifiedObjectInfo>` 对象。
    当 `SimplifiedObjectInfo.is_prefix()` 返回True时，表明是公共前缀（目录）。

    :param str prefix: 只罗列文件名为该前缀的文件
    :param str delimiter: 分隔符。可以用来模拟目录
    :param str continuation_token: 分页标志。首次调用传空串，后续使用返回值的next_continuation_token
    :param str start_after: 起始文件名称，OSS会按照文件的字典序排列返回start_after之后的文件。
    :param bool fetch_owner: 是否获取文件的owner信息，默认不返回。
    :param int max_keys: 最多返回文件的个数，文件和目录的和不能超过该值

    :param headers: HTTP头部
    :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict
    """

    def __init__(
        self,
        bucket: AsyncBucket,
        prefix: str = "",
        delimiter: str = "",
        continuation_token: str = "",
        start_after: str = "",
        fetch_owner: bool = False,
        encoding_type: str = "url",
        max_keys: int = 100,
        max_retries: int | None = None,
        headers: Headers | None = None,
    ):
        super(AsyncObjectIteratorV2, self).__init__(continuation_token, max_retries)

        self.bucket = bucket
        self.prefix = prefix
        self.delimiter = delimiter
        self.start_after = start_after
        self.fetch_owner = fetch_owner
        self.encoding_type = encoding_type
        self.max_keys = max_keys
        self.headers = Headers(headers)

    async def _fetch(self):
        result = await self.bucket.list_objects_v2(
            prefix=self.prefix,
            delimiter=self.delimiter,
            continuation_token=self.next_marker,
            start_after=self.start_after,
            fetch_owner=self.fetch_owner,
            encoding_type=self.encoding_type,
            max_keys=self.max_keys,
            headers=self.headers,
        )
        self.entries = result.object_list + [
            SimplifiedObjectInfo(prefix, 0, "", "", 0, "") for prefix in result.prefix_list
        ]
        self.entries.sort(key=lambda obj: obj.key)

        return result.is_truncated, result.next_continuation_token


class AsyncMultipartUploadIterator(_BaseIterator[MultipartUploadInfo]):
    """遍历Bucket里未完成的分片上传。

    每次返回 :class:`MultipartUploadInfo <oss2.models.MultipartUploadInfo>` 对象。
    当 `MultipartUploadInfo.is_prefix()` 返回True时，表明是公共前缀（目录）。

    :param bucket: :class:`Bucket <oss2.Bucket>` 对象
    :param prefix: 仅列举匹配该前缀的文件的分片上传
    :param delimiter: 目录分隔符
    :param key_marker: 文件名分页符
    :param upload_id_marker: 分片上传ID分页符
    :param max_uploads: 每次调用 `list_multipart_uploads` 时的max_uploads参数。注意迭代器返回的数目可能会大于该值。

    :param headers: HTTP头部
    :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict
    """

    def __init__(
        self,
        bucket: AsyncBucket,
        prefix: str = "",
        delimiter: str = "",
        key_marker: str = "",
        upload_id_marker: str = "",
        max_uploads: int = 1000,
        max_retries: int | None = None,
        headers: Headers | None = None,
    ):
        super(AsyncMultipartUploadIterator, self).__init__(key_marker, max_retries)

        self.bucket = bucket
        self.prefix = prefix
        self.delimiter = delimiter
        self.next_upload_id_marker = upload_id_marker
        self.max_uploads = max_uploads
        self.headers = Headers(headers)

    async def _fetch(self):
        result = await self.bucket.list_multipart_uploads(
            prefix=self.prefix,
            delimiter=self.delimiter,
            key_marker=self.next_marker,
            upload_id_marker=self.next_upload_id_marker,
            max_uploads=self.max_uploads,
            headers=self.headers,
        )
        self.entries = result.upload_list + [MultipartUploadInfo(prefix, None, None) for prefix in result.prefix_list]
        self.entries.sort(key=lambda u: u.key)

        self.next_upload_id_marker = result.next_upload_id_marker
        return result.is_truncated, result.next_key_marker


class AsyncObjectUploadIterator(_BaseIterator[MultipartUploadInfo]):
    """遍历一个Object所有未完成的分片上传。

    每次返回 :class:`MultipartUploadInfo <oss2.models.MultipartUploadInfo>` 对象。
    当 `MultipartUploadInfo.is_prefix()` 返回True时，表明是公共前缀（目录）。

    :param bucket: :class:`Bucket <oss2.Bucket>` 对象
    :param key: 文件名
    :param max_uploads: 每次调用 `list_multipart_uploads` 时的max_uploads参数。注意迭代器返回的数目可能会大于该值。

    :param headers: HTTP头部
    :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict
    """

    def __init__(
        self,
        bucket: AsyncBucket,
        key: str,
        max_uploads: int = 1000,
        max_retries: int | None = None,
        headers: Headers | None = None,
    ):
        super(AsyncObjectUploadIterator, self).__init__("", max_retries)
        self.bucket = bucket
        self.key = key
        self.next_upload_id_marker = ""
        self.max_uploads = max_uploads
        self.headers = Headers(headers)

    async def _fetch(self):
        result = await self.bucket.list_multipart_uploads(
            prefix=self.key,
            key_marker=self.next_marker,
            upload_id_marker=self.next_upload_id_marker,
            max_uploads=self.max_uploads,
            headers=self.headers,
        )

        self.entries = [u for u in result.upload_list if u.key == self.key]
        self.next_upload_id_marker = result.next_upload_id_marker

        if not result.is_truncated or not self.entries:
            return False, result.next_key_marker

        if result.next_key_marker > self.key:
            return False, result.next_key_marker

        return result.is_truncated, result.next_key_marker


class AsyncPartIterator(_BaseIterator[PartInfo]):
    """遍历一个分片上传会话中已经上传的分片。

    每次返回 :class:`PartInfo <oss2.models.PartInfo>` 对象。

    :param bucket: :class:`Bucket <oss2.Bucket>` 对象
    :param key: 文件名
    :param upload_id: 分片上传ID
    :param marker: 分页符
    :param max_parts: 每次调用 `list_parts` 时的max_parts参数。注意迭代器返回的数目可能会大于该值。

    :param headers: HTTP头部
    :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict
    """

    def __init__(
        self,
        bucket: AsyncBucket,
        key: str,
        upload_id: str,
        marker: str = "0",
        max_parts: int = 1000,
        max_retries: int | None = None,
        headers: Headers | None = None,
    ):
        super(AsyncPartIterator, self).__init__(marker, max_retries)

        self.bucket = bucket
        self.key = key
        self.upload_id = upload_id
        self.max_parts = max_parts
        self.headers = Headers(headers)

    async def _fetch(self):
        result = await self.bucket.list_parts(
            self.key, self.upload_id, marker=self.next_marker, max_parts=self.max_parts, headers=self.headers
        )
        self.entries = result.parts

        return result.is_truncated, result.next_marker


class AsyncLiveChannelIterator(_BaseIterator):
    """遍历Bucket里文件的迭代器。

    每次迭代返回的是 :class:`LiveChannelInfo <oss2.models.LiveChannelInfo>` 对象。

    :param bucket: :class:`Bucket <oss2.Bucket>` 对象
    :param prefix: 只列举匹配该前缀的文件
    :param marker: 分页符
    :param max_keys: 每次调用 `list_live_channel` 时的max_keys参数。注意迭代器返回的数目可能会大于该值。
    """

    def __init__(self, bucket, prefix="", marker="", max_keys=100, max_retries=None):
        super(AsyncLiveChannelIterator, self).__init__(marker, max_retries)

        self.bucket = bucket
        self.prefix = prefix
        self.max_keys = max_keys

    async def _fetch(self):
        result = await self.bucket.list_live_channel(
            prefix=self.prefix, marker=self.next_marker, max_keys=self.max_keys
        )
        self.entries = result.channels

        return result.is_truncated, result.next_marker
