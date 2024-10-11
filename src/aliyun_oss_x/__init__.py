import logging

from . import models, exceptions, defaults

from .api import Service, Bucket, AsyncBucket, AsyncService
from .auth import (
    Auth,
    AuthV4,
    AnonymousAuth,
    StsAuth,
    AUTH_VERSION_4,
    make_auth,
    ProviderAuthV4,
)
from .http import Session
from .credentials import (
    EcsRamRoleCredentialsProvider,
    EcsRamRoleCredential,
    CredentialsProvider,
    StaticCredentialsProvider,
)

from .iterators import (
    BucketIterator,
    ObjectIterator,
    ObjectIteratorV2,
    MultipartUploadIterator,
    ObjectUploadIterator,
    PartIterator,
    LiveChannelIterator,
    AsyncBucketIterator,
    AsyncObjectIterator,
    AsyncObjectIteratorV2,
    AsyncMultipartUploadIterator,
    AsyncObjectUploadIterator,
    AsyncPartIterator,
    AsyncLiveChannelIterator,
)

from .resumable.sync_resumable import (
    resumable_upload,
    resumable_download,
    ResumableStore,
    ResumableDownloadStore,
    determine_part_size,
    make_upload_store,
    make_download_store,
)

from .resumable.async_resumable import (
    resumable_upload_async,
    resumable_download_async,
    AsyncResumableStore,
    AsyncResumableDownloadStore,
    make_upload_store_async,
    make_download_store_async,
)

from .compat import to_bytes

from .utils import SizedFileAdapter, make_progress_adapter
from .utils import content_type_by_name, is_valid_bucket_name, is_valid_endpoint
from .utils import http_date, http_to_unixtime, iso8601_to_unixtime, date_to_iso8601, iso8601_to_date


from .models import BUCKET_ACL_PRIVATE, BUCKET_ACL_PUBLIC_READ, BUCKET_ACL_PUBLIC_READ_WRITE
from .models import (
    SERVER_SIDE_ENCRYPTION_AES256,
    SERVER_SIDE_ENCRYPTION_KMS,
    SERVER_SIDE_ENCRYPTION_SM4,
    KMS_DATA_ENCRYPTION_SM4,
)
from .models import OBJECT_ACL_DEFAULT, OBJECT_ACL_PRIVATE, OBJECT_ACL_PUBLIC_READ, OBJECT_ACL_PUBLIC_READ_WRITE
from .models import (
    BUCKET_STORAGE_CLASS_STANDARD,
    BUCKET_STORAGE_CLASS_IA,
    BUCKET_STORAGE_CLASS_ARCHIVE,
    BUCKET_STORAGE_CLASS_COLD_ARCHIVE,
    BUCKET_STORAGE_CLASS_DEEP_COLD_ARCHIVE,
)
from .models import BUCKET_VERSIONING_ENABLE, BUCKET_VERSIONING_SUSPEND
from .models import BUCKET_DATA_REDUNDANCY_TYPE_LRS, BUCKET_DATA_REDUNDANCY_TYPE_ZRS

from .__version__ import __version__

from .crypto import LocalRsaProvider, AliKMSProvider, RsaProvider, EncryptionMaterials
from .crypto_bucket import CryptoBucket, AsyncCryptoBucket

from . import crc64_combine

logger = logging.getLogger("aliyun_oss_x")


def set_file_logger(file_path, name="aliyun_oss_x", level=logging.INFO, format_string=None):
    global logger
    if not format_string:
        format_string = "%(asctime)s %(name)s [%(levelname)s] %(thread)d : %(message)s"
    logger = logging.getLogger(name)
    logger.setLevel(level)
    fh = logging.FileHandler(file_path)
    fh.setLevel(level)
    formatter = logging.Formatter(format_string)
    fh.setFormatter(formatter)
    logger.addHandler(fh)


def set_stream_logger(name="aliyun_oss_x", level=logging.DEBUG, format_string=None):
    global logger
    if not format_string:
        format_string = "%(asctime)s %(name)s [%(levelname)s] %(thread)d : %(message)s"
    logger = logging.getLogger(name)
    logger.setLevel(level)
    fh = logging.StreamHandler()
    fh.setLevel(level)
    formatter = logging.Formatter(format_string)
    fh.setFormatter(formatter)
    logger.addHandler(fh)


__all__ = [
    "models",
    "exceptions",
    "defaults",
    "Bucket",
    "AsyncBucket",
    "Service",
    "AsyncService",
    "Auth",
    "AuthV4",
    "AnonymousAuth",
    "StsAuth",
    "AUTH_VERSION_4",
    "make_auth",
    "ProviderAuthV4",
    "Session",
    "EcsRamRoleCredentialsProvider",
    "EcsRamRoleCredential",
    "CredentialsProvider",
    "StaticCredentialsProvider",
    "BucketIterator",
    "ObjectIterator",
    "ObjectIteratorV2",
    "MultipartUploadIterator",
    "ObjectUploadIterator",
    "PartIterator",
    "LiveChannelIterator",
    "AsyncBucketIterator",
    "AsyncObjectIterator",
    "AsyncObjectIteratorV2",
    "AsyncMultipartUploadIterator",
    "AsyncObjectUploadIterator",
    "AsyncPartIterator",
    "AsyncLiveChannelIterator",
    "to_bytes",
    "SizedFileAdapter",
    "make_progress_adapter",
    "content_type_by_name",
    "is_valid_bucket_name",
    "is_valid_endpoint",
    "http_date",
    "http_to_unixtime",
    "iso8601_to_unixtime",
    "date_to_iso8601",
    "iso8601_to_date",
    "BUCKET_ACL_PRIVATE",
    "BUCKET_ACL_PUBLIC_READ",
    "BUCKET_ACL_PUBLIC_READ_WRITE",
    "SERVER_SIDE_ENCRYPTION_AES256",
    "SERVER_SIDE_ENCRYPTION_KMS",
    "SERVER_SIDE_ENCRYPTION_SM4",
    "KMS_DATA_ENCRYPTION_SM4",
    "OBJECT_ACL_DEFAULT",
    "OBJECT_ACL_PRIVATE",
    "OBJECT_ACL_PUBLIC_READ",
    "OBJECT_ACL_PUBLIC_READ_WRITE",
    "BUCKET_STORAGE_CLASS_STANDARD",
    "BUCKET_STORAGE_CLASS_IA",
    "BUCKET_STORAGE_CLASS_ARCHIVE",
    "BUCKET_STORAGE_CLASS_COLD_ARCHIVE",
    "BUCKET_STORAGE_CLASS_DEEP_COLD_ARCHIVE",
    "BUCKET_VERSIONING_ENABLE",
    "BUCKET_VERSIONING_SUSPEND",
    "BUCKET_DATA_REDUNDANCY_TYPE_LRS",
    "BUCKET_DATA_REDUNDANCY_TYPE_ZRS",
    "resumable_upload",
    "resumable_download",
    "ResumableStore",
    "ResumableDownloadStore",
    "determine_part_size",
    "make_upload_store",
    "make_download_store",
    "resumable_upload_async",
    "resumable_download_async",
    "AsyncResumableStore",
    "AsyncResumableDownloadStore",
    "make_upload_store_async",
    "make_download_store_async",
    "LocalRsaProvider",
    "AliKMSProvider",
    "RsaProvider",
    "EncryptionMaterials",
    "CryptoBucket",
    "AsyncCryptoBucket",
    "crc64_combine",
    "__version__",
]
