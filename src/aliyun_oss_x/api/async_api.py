import shutil
import logging
from urllib.parse import quote
from typing import Type, Callable

from .. import http
from .. import utils
from .. import defaults
from .. import xml_utils
from .. import exceptions

from ..models import (
    ListBucketsResult,
    GetUserQosInfoResult,
    DescribeRegionsResult,
    RequestResult,
    ListUserDataRedundancyTransitionResult,
    GetPublicAccessBlockResult,
    ListResourcePoolsResult,
    ResourcePoolInfoResult,
    ListResourcePoolBucketsResult,
    RequesterQoSInfoResult,
    ListResourcePoolRequesterQoSInfosResult,
    ListObjectsResult,
    ListObjectsV2Result,
    PutObjectResult,
    AppendObjectResult,
    GetObjectResult,
    SelectObjectResult,
    HeadObjectResult,
    GetSelectObjectMetaResult,
    GetObjectMetaResult,
    RestoreConfiguration,
    GetObjectAclResult,
    BatchDeleteObjectsResult,
    InitMultipartUploadResult,
    ListMultipartUploadsResult,
    ListPartsResult,
    GetSymlinkResult,
    BucketCreateConfig,
    GetBucketAclResult,
    BucketCors,
    LiveChannelInfo,
    GetBucketLocationResult,
    BucketLogging,
    GetBucketLoggingResult,
    BucketReferer,
    GetBucketRefererResult,
    GetBucketStatResult,
    GetBucketInfoResult,
    GetBucketWebsiteResult,
    CreateLiveChannelResult,
    GetLiveChannelResult,
    ListLiveChannelResult,
    GetLiveChannelStatResult,
    GetLiveChannelHistoryResult,
    GetVodPlaylistResult,
    ProcessObjectResult,
    GetTaggingResult,
    GetBucketCorsResult,
    BucketLifecycle,
    GetBucketLifecycleResult,
    GetServerSideEncryptionResult,
    Tagging,
    ServerSideEncryptionRule,
    ListObjectVersionsResult,
    BucketVersioningConfig,
    GetBucketVersioningResult,
    GetBucketPolicyResult,
    GetBucketRequestPaymentResult,
    BucketQosInfo,
    GetBucketQosInfoResult,
    BucketWebsite,
    InventoryConfiguration,
    ListAccessPointResult,
    GetBucketUserQosResult,
    PutAsyncFetchTaskResult,
    GetAsyncFetchTaskResult,
    GetInventoryConfigurationResult,
    ListInventoryConfigurationsResult,
    InitBucketWormResult,
    GetBucketWormResult,
    GetBucketReplicationResult,
    GetBucketReplicationLocationResult,
    GetBucketReplicationProgressResult,
    GetBucketTransferAccelerationResult,
    CreateBucketCnameTokenResult,
    GetBucketCnameTokenResult,
    ListBucketCnameResult,
    GetBucketMetaQueryResult,
    MetaQuery,
    DoBucketMetaQueryResult,
    GetBucketAccessMonitorResult,
    GetBucketResourceGroupResult,
    GetBucketStyleResult,
    ListBucketStyleResult,
    AsyncProcessObject,
    CallbackPolicyResult,
    GetBucketArchiveDirectReadResult,
    CreateDataRedundancyTransitionResult,
    DataRedundancyTransitionInfoResult,
    HttpsConfigResult,
    ListBucketDataRedundancyTransitionResult,
    CreateAccessPointResult,
    GetAccessPointResult,
    GetAccessPointPolicyResult,
    GetBucketPublicAccessBlockResult,
    ListBucketRequesterQoSInfosResult,
)
from ..headers import (
    OSS_CANNED_ACL,
    OSS_COPY_OBJECT_SOURCE,
    OSS_COPY_OBJECT_SOURCE_RANGE,
    OSS_OBJECT_ACL,
    OSS_SYMLINK_TARGET,
    OSS_TASK_ID,
    OSS_METADATA_DIRECTIVE,
)
from ..exceptions import ClientError
from ..compat import to_unicode, to_string
from ..select_params import SelectParameters
from ..auth import AnonymousAuth, StsAuth, ProviderAuthV4
from ._types import ResultType, ProxiesTypes
from ._utils import _make_range_string, _normalize_endpoint, _UrlMaker


logger = logging.getLogger(__name__)


class _Base:
    def __init__(
        self,
        auth: AnonymousAuth | StsAuth | ProviderAuthV4,
        endpoint: str,
        is_cname: bool,
        session: http.AsyncSession | None = None,
        connect_timeout: int | None = None,
        app_name: str = "",
        enable_crc: bool = True,
        proxies: ProxiesTypes | None = None,
        region: str | None = None,
        cloudbox_id: str | None = None,
        is_path_style: bool = False,
        is_verify_object_strict: bool = True,
    ):
        self.auth = auth
        self.endpoint = _normalize_endpoint(endpoint.strip())
        if utils.is_valid_endpoint(self.endpoint) is not True:
            raise ClientError(f"The endpoint you has specified is not valid, endpoint: {endpoint}")
        self.session = session or http.AsyncSession()
        self.timeout = defaults.get(connect_timeout, defaults.connect_timeout)
        self.app_name = app_name
        self.enable_crc = enable_crc
        self.proxies = proxies
        self.region = region
        self.product = "oss"
        self.cloudbox_id = cloudbox_id
        if self.cloudbox_id is not None:
            self.product = "oss-cloudbox"
        self._make_url = _UrlMaker(self.endpoint, is_cname, is_path_style)
        self.is_verify_object_strict = is_verify_object_strict
        if hasattr(self.auth, "auth_version") and self.auth.auth_version() != "v1":
            self.is_verify_object_strict = False

    async def _do(self, method, bucket_name, key, **kwargs):
        key = to_string(key)
        req = http.AsyncRequest(
            method,
            self._make_url(bucket_name, key),
            app_name=self.app_name,
            proxies=self.proxies,
            region=self.region,
            product=self.product,
            cloudbox_id=self.cloudbox_id,
            **kwargs,
        )
        self.auth._sign_request(req, bucket_name, key)

        resp = await self.session.do_request(req, timeout=self.timeout)
        if resp.status // 100 != 2:
            e = exceptions.make_exception(resp)
            logger.info(f"Exception: {e}")
            raise e

        return resp

    async def _do_url(self, method, sign_url, **kwargs):
        req = http.AsyncRequest(method, sign_url, app_name=self.app_name, proxies=self.proxies, **kwargs)
        resp = await self.session.do_request(req, timeout=self.timeout)
        if resp.status // 100 != 2:
            e = exceptions.make_exception(resp)
            logger.info(f"Exception: {e}")
            raise e

        return resp

    @staticmethod
    def _parse_result(resp, parse_func: Callable[[ResultType, bytes], None], class_: Type[ResultType]) -> ResultType:
        result = class_(resp)
        parse_func(result, resp.read())
        return result


class AsyncService(_Base):
    """用于Service操作的类，如罗列用户所有的Bucket。

    用法 ::

        >>> import oss2
        >>> auth = oss2.Auth('your-access-key-id', 'your-access-key-secret')
        >>> service = oss2.Service(auth, 'oss-cn-hangzhou.aliyuncs.com')
        >>> service.list_buckets()
        <oss2.models.ListBucketsResult object at 0x0299FAB0>

    :param auth: 包含了用户认证信息的Auth对象
    :type auth: oss2.Auth

    :param str endpoint: 访问域名，如杭州区域的域名为oss-cn-hangzhou.aliyuncs.com

    :param session: 会话。如果是None表示新开会话，非None则复用传入的会话
    :type session: oss2.Session

    :param float connect_timeout: 连接超时时间，以秒为单位。
    :param str app_name: 应用名。该参数不为空，则在User Agent中加入其值。
        注意到，最终这个字符串是要作为HTTP Header的值传输的，所以必须要遵循HTTP标准。
    """

    QOS_INFO = "qosInfo"
    REGIONS = "regions"
    WRITE_GET_OBJECT_RESPONSE = "x-oss-write-get-object-response"
    PUBLIC_ACCESS_BLOCK = "publicAccessBlock"
    REQUESTER_QOS_INFO = "requesterQosInfo"
    QOS_REQUESTER = "qosRequester"
    RESOURCE_POOL_INFO = "resourcePoolInfo"
    RESOURCE_POOL = "resourcePool"
    RESOURCE_POOL_BUCKETS = "resourcePoolBuckets"

    def __init__(
        self,
        auth,
        endpoint,
        session=None,
        connect_timeout=None,
        app_name="",
        proxies=None,
        region=None,
        cloudbox_id=None,
        is_path_style=False,
    ):
        logger.debug(
            f"Init oss service, endpoint: {endpoint}, connect_timeout: {connect_timeout}, app_name: {app_name}, proxies: {proxies}"
        )
        super(AsyncService, self).__init__(
            auth,
            endpoint,
            False,
            session,
            connect_timeout,
            app_name=app_name,
            proxies=proxies,
            region=region,
            cloudbox_id=cloudbox_id,
            is_path_style=is_path_style,
        )

    async def list_buckets(self, prefix="", marker="", max_keys=100, params=None, headers=None):
        """根据前缀罗列用户的Bucket。

        :param str prefix: 只罗列Bucket名为该前缀的Bucket，空串表示罗列所有的Bucket
        :param str marker: 分页标志。首次调用传空串，后续使用返回值中的next_marker
        :param int max_keys: 每次调用最多返回的Bucket数目
        :param dict params: list操作参数，传入'tag-key','tag-value'对结果进行过滤
        :param headers: 用户指定的HTTP头部。可以指定Content-Type、Content-MD5、x-oss-meta-开头的头部等。可以是dict，建议是oss2.CaseInsensitiveDict

        :return: 罗列的结果
        :rtype: oss2.models.ListBucketsResult
        """
        logger.debug(f"Start to list buckets, prefix: {prefix}, marker: {marker}, max-keys: {max_keys}")

        listParam = {}
        listParam["prefix"] = prefix
        listParam["marker"] = marker
        listParam["max-keys"] = str(max_keys)

        headers = http.Headers(headers)

        if params is not None:
            listParam.update(params)

        resp = await self._do("GET", "", "", params=listParam, headers=headers)
        logger.debug(f"List buckets done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_list_buckets, ListBucketsResult)

    async def get_user_qos_info(self):
        """获取User的QoSInfo
        :return: :class:`GetUserQosInfoResult <oss2.models.GetUserQosInfoResult>`
        """
        logger.debug("Start to get user qos info.")
        resp = await self._do("GET", "", "", params={AsyncService.QOS_INFO: ""})
        logger.debug(f"get use qos, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_qos_info, GetUserQosInfoResult)

    async def describe_regions(self, regions=""):
        """查询所有支持地域或者指定地域对应的Endpoint信息，包括外网Endpoint、内网Endpoint和传输加速Endpoint。

        :param str regions : 地域。
        :return: :class:`DescribeRegionsResult <oss2.models.DescribeRegionsResult>`
        """
        logger.debug("Start to describe regions")

        resp = await self._do("GET", "", "", params={AsyncService.REGIONS: regions})
        logger.debug(f"Describe regions done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_describe_regions, DescribeRegionsResult)

    async def write_get_object_response(self, route, token, fwd_status, data, headers=None):
        """write get object response.
        :param route: fc return route
        :param token: fc return token
        :param fwd_status: fwd_status

        :param data: 待上传的内容。
        :type data: bytes，str或file-like object

        :param headers: 用户指定的HTTP头部。可以指定Content-Type、Content-MD5、x-oss-meta-开头的头部等
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """

        logger.debug(f"Start to write get object response, headers: {headers}")

        headers = http.Headers(headers)

        if route:
            headers["x-oss-request-route"] = route
        if token:
            headers["x-oss-request-token"] = token
        if fwd_status:
            headers["x-oss-fwd-status"] = fwd_status

        resp = await self._do(
            "POST", "", "", params={AsyncService.WRITE_GET_OBJECT_RESPONSE: ""}, headers=headers, data=data
        )
        logger.debug(f"write get object response done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def list_user_data_redundancy_transition(self, continuation_token="", max_keys=100):
        """列举请求者所有的存储冗余转换任务。

        :param str continuation_token: 分页标志,首次调用传空串
        :param int max_keys: 最多返回数目

        :return: :class:`ListUserDataRedundancyTransitionResult <oss2.models.ListUserDataRedundancyTransitionResult>`
        """
        logger.debug(
            f"Start to list user data redundancy transition, continuation token: {continuation_token}, max keys: {max_keys}"
        )

        resp = await self._do(
            "GET",
            "",
            "",
            params={
                AsyncBucket.REDUNDANCY_TRANSITION: "",
                "continuation-token": continuation_token,
                "max-keys": str(max_keys),
            },
        )
        logger.debug(
            f"List user data redundancy transition done, req_id: {resp.request_id}, status_code: {resp.status}"
        )
        return self._parse_result(
            resp, xml_utils.parse_list_user_data_redundancy_transition, ListUserDataRedundancyTransitionResult
        )

    async def list_access_points(self, max_keys=100, continuation_token=""):
        """查询某个Bucket下所有接入点。
        param: int max_keys: 本次list返回access point的最大个数
        param: str continuation_token: list时指定的起始标记

        :return: :class:`ListBucketStyleResult <oss2.models.ListBucketStyleResult>`
        """

        logger.debug("Start to list bucket access point")
        resp = await self._do(
            "GET",
            "",
            "",
            params={AsyncBucket.ACCESS_POINT: "", "max-keys": str(max_keys), "continuation-token": continuation_token},
        )
        logger.debug(f"query list access point done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_list_access_point_result, ListAccessPointResult)

    async def put_public_access_block(self, block_public_access=False):
        """为OSS全局开启阻止公共访问。

        :param bool block_public_access : 是否开启阻止公共访问。
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug("Start to put public access block")

        data = xml_utils.to_put_public_access_block_request(block_public_access)
        resp = await self._do("PUT", "", "", data=data, params={AsyncService.PUBLIC_ACCESS_BLOCK: ""})
        logger.debug(f"Put public access block done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_public_access_block(self):
        """获取OSS全局阻止公共访问的配置信息。

        :return: :class:`GetPublicAccessBlockResult <oss2.models.GetPublicAccessBlockResult>`
        """
        logger.debug("Start to get public access block")

        resp = await self._do("GET", "", "", params={AsyncService.PUBLIC_ACCESS_BLOCK: ""})
        logger.debug(f"Get public access block done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_get_public_access_block_result, GetPublicAccessBlockResult)

    async def delete_public_access_block(self):
        """删除OSS全局阻止公共访问配置信息。

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug("Start to delete public access block")

        resp = await self._do("DELETE", "", "", params={AsyncService.PUBLIC_ACCESS_BLOCK: ""})
        logger.debug(f"Delete public access block done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def list_resource_pools(self, continuation_token="", max_keys=100):
        """列举当前主账号在当前地域下的资源池。

        :param str continuation_token: 分页标志,首次调用传空串
        :param int max_keys: 最多返回数目

        :return: :class:`ListResourcePoolsResult <oss2.models.ListResourcePoolsResult>`
        """
        logger.debug(f"Start to list resource pools, continuation_token: {continuation_token}, max_keys: {max_keys}")

        resp = await self._do(
            "GET",
            "",
            "",
            params={
                AsyncService.RESOURCE_POOL: "",
                "continuation-token": continuation_token,
                "max-keys": str(max_keys),
            },
        )
        logger.debug(f"List resource pools done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_list_resource_pools, ListResourcePoolsResult)

    async def get_resource_pool_info(self, resource_pool_name):
        """获取特定资源池的基本信息。

        :param str resource_pool_name : 请求的资源池的名称。
        :return: :class:`ResourcePoolInfoResult <oss2.models.ResourcePoolInfoResult>`
        """
        logger.debug(f"Start to get resource pool info, uid: {resource_pool_name}.")
        if not resource_pool_name:
            raise ClientError("resource_pool_name should not be empty")

        resp = await self._do(
            "GET", "", "", params={AsyncService.RESOURCE_POOL_INFO: "", AsyncService.RESOURCE_POOL: resource_pool_name}
        )
        logger.debug(f"Get resource pool info done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_get_resource_pool_info, ResourcePoolInfoResult)

    async def list_resource_pool_buckets(self, resource_pool_name, continuation_token="", max_keys=100):
        """获取特定资源池中的Bucket列表。

        :param str resource_pool_name : 请求的资源池的名称。
        :param str continuation_token: 分页标志,首次调用传空串
        :param int max_keys: 最多返回数目

        :return: :class:`ListResourcePoolBucketsResult <oss2.models.ListResourcePoolBucketsResult>`
        """
        logger.debug(
            f"Start to list resource pool buckets, resource_pool_name:{resource_pool_name} continuation_token: {continuation_token}, max_keys: {max_keys}"
        )
        if not resource_pool_name:
            raise ClientError("resource_pool_name should not be empty")

        resp = await self._do(
            "GET",
            "",
            "",
            params={
                AsyncService.RESOURCE_POOL_BUCKETS: "",
                AsyncService.RESOURCE_POOL: resource_pool_name,
                "continuation-token": continuation_token,
                "max-keys": str(max_keys),
            },
        )
        logger.debug(f"List resource pool buckets done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_list_resource_pool_buckets, ListResourcePoolBucketsResult)

    async def put_resource_pool_requester_qos_info(self, uid, resource_pool_name, qos_configuration):
        """修改子账号在资源池的请求者流控配置。

        :param str uid: 请求者UID
        :param str resource_pool_name: 请求的资源池的名称
        :param qos_configuration :class:`QoSConfiguration <oss2.models.QoSConfiguration>`
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(
            f"Start to put resource pool requester qos info, uid: {uid}, resource_pool_name: {resource_pool_name}, qos_configuration: {qos_configuration}"
        )
        if not uid:
            raise ClientError("uid should not be empty")
        if not resource_pool_name:
            raise ClientError("resource_pool_name should not be empty")

        data = xml_utils.to_put_qos_info(qos_configuration)
        resp = await self._do(
            "PUT",
            "",
            "",
            data=data,
            params={
                AsyncService.REQUESTER_QOS_INFO: "",
                AsyncService.QOS_REQUESTER: uid,
                AsyncService.RESOURCE_POOL: resource_pool_name,
            },
        )
        logger.debug(
            f"Put resource pool requester qos info done, req_id: {resp.request_id}, status_code: {resp.status}"
        )
        return RequestResult(resp)

    async def get_resource_pool_requester_qos_info(self, uid, resource_pool_name):
        """获取子账号在资源池的流控配置。

        :return: :class:`RequesterQoSInfoResult <oss2.models.RequesterQoSInfoResult>`
        """
        logger.debug(
            f"Start to get resource pool requester qos info, uid: {uid}, resource_pool_name: {resource_pool_name}."
        )
        if not uid:
            raise ClientError("uid should not be empty")
        if not resource_pool_name:
            raise ClientError("resource_pool_name should not be empty")

        resp = await self._do(
            "GET",
            "",
            "",
            params={
                AsyncService.REQUESTER_QOS_INFO: "",
                AsyncService.QOS_REQUESTER: uid,
                AsyncService.RESOURCE_POOL: resource_pool_name,
            },
        )
        logger.debug(
            f"Get resource pool requester qos info done, req_id: {resp.request_id}, status_code: {resp.status}"
        )

        return self._parse_result(resp, xml_utils.parse_get_requester_qos_info, RequesterQoSInfoResult)

    async def list_resource_pool_requester_qos_infos(self, resource_pool_name, continuation_token="", max_keys=100):
        """列举子账号账号在资源池的流控配置。

        :param str resource_pool_name : 请求的资源池的名称。
        :param str continuation_token: 分页标志,首次调用传空串
        :param int max_keys: 最多返回数目

        :return: :class:`ListResourcePoolRequesterQoSInfosResult <oss2.models.ListResourcePoolRequesterQoSInfosResult>`
        """
        logger.debug(
            f"Start to list resource pool requester qos infos, resource_pool_name:{resource_pool_name} continuation_token: {continuation_token}, max_keys: {max_keys}"
        )
        if not resource_pool_name:
            raise ClientError("resource_pool_name should not be empty")

        resp = await self._do(
            "GET",
            "",
            "",
            params={
                AsyncService.REQUESTER_QOS_INFO: "",
                AsyncService.RESOURCE_POOL: resource_pool_name,
                "continuation-token": continuation_token,
                "max-keys": str(max_keys),
            },
        )
        logger.debug(
            f"List resource pool requester qos infos done, req_id: {resp.request_id}, status_code: {resp.status}"
        )
        return self._parse_result(
            resp, xml_utils.parse_list_resource_pool_requester_qos_infos, ListResourcePoolRequesterQoSInfosResult
        )

    async def delete_resource_pool_requester_qos_info(self, uid, resource_pool_name):
        """删除子账号在资源池的请求者流控配置。

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(
            f"Start to delete resource pool requester qos info, uid: {uid}, resource_pool_name: {resource_pool_name}."
        )
        if not uid:
            raise ClientError("uid should not be empty")

        if not resource_pool_name:
            raise ClientError("resource_pool_name should not be empty")

        resp = await self._do(
            "DELETE",
            "",
            "",
            params={
                AsyncService.REQUESTER_QOS_INFO: "",
                AsyncService.QOS_REQUESTER: uid,
                AsyncService.RESOURCE_POOL: resource_pool_name,
            },
        )
        logger.debug(
            f"Delete resource pool requester qos info done, req_id: {resp.request_id}, status_code: {resp.status}"
        )

        return RequestResult(resp)


class AsyncBucket(_Base):
    """用于Bucket和Object操作的类，诸如创建、删除Bucket，上传、下载Object等。

    用法（假设Bucket属于杭州区域） ::

        >>> import oss2
        >>> auth = oss2.Auth('your-access-key-id', 'your-access-key-secret')
        >>> bucket = oss2.Bucket(auth, 'http://oss-cn-hangzhou.aliyuncs.com', 'your-bucket')
        >>> bucket.put_object('readme.txt', 'content of the object')
        <oss2.models.PutObjectResult object at 0x029B9930>

    :param auth: 包含了用户认证信息的Auth对象
    :type auth: oss2.Auth

    :param str endpoint: 访问域名或者CNAME
    :param str bucket_name: Bucket名
    :param bool is_cname: 如果endpoint是CNAME则设为True；反之，则为False。

    :param session: 会话。如果是None表示新开会话，非None则复用传入的会话
    :type session: oss2.Session

    :param float connect_timeout: 连接超时时间，以秒为单位。

    :param str app_name: 应用名。该参数不为空，则在User Agent中加入其值。
        注意到，最终这个字符串是要作为HTTP Header的值传输的，所以必须要遵循HTTP标准。

    :param bool is_verify_object_strict: 严格验证对象名称的标志。默认为True。
    """

    ACL = "acl"
    CORS = "cors"
    LIFECYCLE = "lifecycle"
    LOCATION = "location"
    LOGGING = "logging"
    REFERER = "referer"
    WEBSITE = "website"
    LIVE = "live"
    COMP = "comp"
    STATUS = "status"
    VOD = "vod"
    SYMLINK = "symlink"
    STAT = "stat"
    BUCKET_INFO = "bucketInfo"
    PROCESS = "x-oss-process"
    TAGGING = "tagging"
    ENCRYPTION = "encryption"
    VERSIONS = "versions"
    VERSIONING = "versioning"
    VERSIONID = "versionId"
    RESTORE = "restore"
    OBJECTMETA = "objectMeta"
    POLICY = "policy"
    REQUESTPAYMENT = "requestPayment"
    QOS_INFO = "qosInfo"
    USER_QOS = "qos"
    ASYNC_FETCH = "asyncFetch"
    SEQUENTIAL = "sequential"
    INVENTORY = "inventory"
    INVENTORY_CONFIG_ID = "inventoryId"
    CONTINUATION_TOKEN = "continuation-token"
    WORM = "worm"
    WORM_ID = "wormId"
    WORM_EXTEND = "wormExtend"
    REPLICATION = "replication"
    REPLICATION_LOCATION = "replicationLocation"
    REPLICATION_PROGRESS = "replicationProgress"
    TRANSFER_ACCELERATION = "transferAcceleration"
    CNAME = "cname"
    META_QUERY = "metaQuery"
    ACCESS_MONITOR = "accessmonitor"
    RESOURCE_GROUP = "resourceGroup"
    STYLE = "style"
    STYLE_NAME = "styleName"
    ASYNC_PROCESS = "x-oss-async-process"
    CALLBACK = "callback"
    ARCHIVE_DIRECT_READ = "bucketArchiveDirectRead"
    HTTPS_CONFIG = "httpsConfig"
    REDUNDANCY_TRANSITION = "redundancyTransition"
    TARGET_REDUNDANCY_TYPE = "x-oss-target-redundancy-type"
    REDUNDANCY_TRANSITION_TASK_ID = "x-oss-redundancy-transition-taskid"
    ACCESS_POINT = "accessPoint"
    ACCESS_POINT_POLICY = "accessPointPolicy"
    OSS_ACCESS_POINT_NAME = "x-oss-access-point-name"
    PUBLIC_ACCESS_BLOCK = "publicAccessBlock"
    OSS_ACCESS_POINT_NAME = "x-oss-access-point-name"
    REQUESTER_QOS_INFO = "requesterQosInfo"
    QOS_REQUESTER = "qosRequester"
    RESOURCE_POOL_INFO = "resourcePoolInfo"
    RESOURCE_POOL = "resourcePool"

    def __init__(
        self,
        auth,
        endpoint,
        bucket_name,
        is_cname=False,
        session=None,
        connect_timeout=None,
        app_name="",
        enable_crc=True,
        proxies=None,
        region=None,
        cloudbox_id=None,
        is_path_style=False,
        is_verify_object_strict=True,
    ):
        logger.debug(
            f"Init Bucket: {bucket_name}, endpoint: {endpoint}, isCname: {is_cname}, connect_timeout: {connect_timeout}, app_name: {app_name}, enabled_crc: {enable_crc}, region: {region}, proxies: {region}"
        )
        super(AsyncBucket, self).__init__(
            auth,
            endpoint,
            is_cname,
            session,
            connect_timeout,
            app_name=app_name,
            enable_crc=enable_crc,
            proxies=proxies,
            region=region,
            cloudbox_id=cloudbox_id,
            is_path_style=is_path_style,
            is_verify_object_strict=is_verify_object_strict,
        )

        self.bucket_name = bucket_name.strip()
        if utils.is_valid_bucket_name(self.bucket_name) is not True:
            raise ClientError("The bucket_name is invalid, please check it.")

    def sign_url(self, method, key, expires, headers=None, params=None, slash_safe=False, additional_headers=None):
        """生成签名URL。

        常见的用法是生成加签的URL以供授信用户下载，如为log.jpg生成一个5分钟后过期的下载链接::

            >> bucket.sign_url('GET', 'log.jpg', 5 * 60)
            r'http://your-bucket.oss-cn-hangzhou.aliyuncs.com/logo.jpg?OSSAccessKeyId=YourAccessKeyId&Expires=1447178011&Signature=UJfeJgvcypWq6Q%2Bm3IJcSHbvSak%3D'

        :param method: HTTP方法，如'GET'、'PUT'、'DELETE'等
        :type method: str
        :param key: 文件名
        :param expires: 过期时间（单位：秒），链接在当前时间再过expires秒后过期

        :param headers: 需要签名的HTTP头部，如名称以x-oss-meta-开头的头部（作为用户自定义元数据）、
            Content-Type头部等。对于下载，不需要填。
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :param params: 需要签名的HTTP查询参数

        :param slash_safe: 是否开启key名称中的‘/’转义保护，如果不开启'/'将会转义成%2F
        :type slash_safe: bool

        :param additional_headers: 额外的需要签名的HTTP头

        :return: 签名URL。
        """
        if key is None or len(key.strip()) <= 0:
            raise ClientError("The key is invalid, please check it.")
        key = to_string(key)

        if self.is_verify_object_strict and key.startswith("?"):
            raise ClientError("The key cannot start with `?`, please check it.")

        logger.debug(
            f"Start to sign_url, method: {method}, bucket: {self.bucket_name}, key: {key}, expires: {expires}, headers: {headers}, params: {params}, slash_safe: {slash_safe}"
        )
        req = http.AsyncRequest(
            method,
            self._make_url(self.bucket_name, key, slash_safe),
            headers=headers,
            params=params,
            region=self.region,
            product=self.product,
            cloudbox_id=self.cloudbox_id,
        )
        sign_url = ""
        if additional_headers is None:
            sign_url = self.auth._sign_url(req, self.bucket_name, key, expires)
        else:
            sign_url = self.auth._sign_url(
                req, self.bucket_name, key, expires, in_additional_headers=additional_headers
            )
        return sign_url

    def sign_rtmp_url(self, channel_name, playlist_name, expires):
        """生成RTMP推流的签名URL。
        常见的用法是生成加签的URL以供授信用户向OSS推RTMP流。

        :param channel_name: 直播频道的名称
        :param expires: 过期时间（单位：秒），链接在当前时间再过expires秒后过期
        :param playlist_name: 播放列表名称，注意与创建live channel时一致
        :param params: 需要签名的HTTP查询参数

        :return: 签名URL。
        """
        logger.debug(
            f"Sign RTMP url, bucket: {self.bucket_name}, channel_name: {channel_name}, playlist_name: {playlist_name}, expires: {expires}"
        )
        url = (
            self._make_url(self.bucket_name, "live").replace("http://", "rtmp://").replace("https://", "rtmp://")
            + "/"
            + channel_name
        )
        params = {}
        if playlist_name is not None and playlist_name != "":
            params["playlistName"] = playlist_name
        return self.auth._sign_rtmp_url(url, self.bucket_name, channel_name, expires, params)

    async def list_objects(self, prefix="", delimiter="", marker="", max_keys=100, headers=None):
        """根据前缀罗列Bucket里的文件。

        :param str prefix: 只罗列文件名为该前缀的文件
        :param str delimiter: 分隔符。可以用来模拟目录
        :param str marker: 分页标志。首次调用传空串，后续使用返回值的next_marker
        :param int max_keys: 最多返回文件的个数，文件和目录的和不能超过该值

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`ListObjectsResult <oss2.models.ListObjectsResult>`
        """
        headers = http.Headers(headers)
        logger.debug(
            f"Start to List objects, bucket: {self.bucket_name}, prefix: {prefix}, delimiter: {delimiter}, marker: {marker}, max-keys: {max_keys}"
        )
        resp = await self.__do_bucket(
            "GET",
            params={
                "prefix": prefix,
                "delimiter": delimiter,
                "marker": marker,
                "max-keys": str(max_keys),
                "encoding-type": "url",
            },
            headers=headers,
        )
        logger.debug(f"List objects done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_list_objects, ListObjectsResult)

    async def list_objects_v2(
        self,
        prefix="",
        delimiter="",
        continuation_token="",
        start_after="",
        fetch_owner=False,
        encoding_type="url",
        max_keys=100,
        headers=None,
    ):
        """根据前缀罗列Bucket里的文件。

        :param str prefix: 只罗列文件名为该前缀的文件
        :param str delimiter: 分隔符。可以用来模拟目录
        :param str continuation_token: 分页标志。首次调用传空串，后续使用返回值的next_continuation_token
        :param str start_after: 起始文件名称，OSS会返回按照字典序排列start_after之后的文件。
        :param bool fetch_owner: 是否获取文件的owner信息，默认不返回。
        :param int max_keys: 最多返回文件的个数，文件和目录的和不能超过该值

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`ListObjectsV2Result <oss2.models.ListObjectsV2Result>`
        """
        headers = http.Headers(headers)
        logger.debug(
            f"Start to List objects, bucket: {self.bucket_name}, prefix: {prefix}, delimiter: {delimiter}, continuation_token: {continuation_token}, "
            f"start-after: {start_after}, fetch-owner: {fetch_owner}, encoding_type: {encoding_type}, max-keys: {max_keys}"
        )
        resp = await self.__do_bucket(
            "GET",
            params={
                "list-type": "2",
                "prefix": prefix,
                "delimiter": delimiter,
                "continuation-token": continuation_token,
                "start-after": start_after,
                "fetch-owner": str(fetch_owner).lower(),
                "max-keys": str(max_keys),
                "encoding-type": encoding_type,
            },
            headers=headers,
        )
        logger.debug(f"List objects V2 done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_list_objects_v2, ListObjectsV2Result)

    async def put_object(self, key, data, headers=None, progress_callback=None):
        """上传一个普通文件。

        用法 ::
            >>> bucket.put_object('readme.txt', 'content of readme.txt')
            >>> with open(u'local_file.txt', 'rb') as f:
            >>>     bucket.put_object('remote_file.txt', f)

        :param key: 上传到OSS的文件名

        :param data: 待上传的内容。
        :type data: bytes，str或file-like object

        :param headers: 用户指定的HTTP头部。可以指定Content-Type、Content-MD5、x-oss-meta-开头的头部等
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :param progress_callback: 用户指定的进度回调函数。可以用来实现进度条等功能。参考 :ref:`progress_callback` 。

        :return: :class:`PutObjectResult <oss2.models.PutObjectResult>`
        """
        headers = utils.set_content_type(http.Headers(headers), key)

        if progress_callback:
            data = utils.make_progress_adapter_async(data, progress_callback)

        if self.enable_crc:
            data = utils.make_crc_adapter_async(data)

        logger.debug(f"Start to put object, bucket: {self.bucket_name}, key: {key}, headers: {headers}")
        resp = await self.__do_object("PUT", key, data=data, headers=headers)
        logger.debug(f"Put object done, req_id: {resp.request_id}, status_code: {resp.status}")
        result = PutObjectResult(resp)

        if self.enable_crc and result.crc is not None:
            utils.check_crc("put object", data.crc, result.crc, result.request_id)

        return result

    async def put_object_from_file(self, key, filename, headers=None, progress_callback=None):
        """上传一个本地文件到OSS的普通文件。

        :param str key: 上传到OSS的文件名
        :param str filename: 本地文件名，需要有可读权限

        :param headers: 用户指定的HTTP头部。可以指定Content-Type、Content-MD5、x-oss-meta-开头的头部等
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :param progress_callback: 用户指定的进度回调函数。参考 :ref:`progress_callback`

        :return: :class:`PutObjectResult <oss2.models.PutObjectResult>`
        """
        headers = utils.set_content_type(http.Headers(headers), filename)
        logger.debug(f"Put object from file, bucket: {self.bucket_name}, key: {key}, file path: {filename}")
        with open(to_unicode(filename), "rb") as f:
            return await self.put_object(key, f, headers=headers, progress_callback=progress_callback)

    async def put_object_with_url(self, sign_url, data, headers=None, progress_callback=None):
        """使用加签的url上传对象

        :param sign_url: 加签的url
        :param data: 待上传的数据
        :param headers: 用户指定的HTTP头部。可以指定Content-Type、Content-MD5、x-oss-meta-开头的头部等，必须和签名时保持一致
        :param progress_callback: 用户指定的进度回调函数。参考 :ref:`progress_callback`
        :return:
        """
        headers = http.Headers(headers)

        if progress_callback:
            data = utils.make_progress_adapter_async(data, progress_callback)

        if self.enable_crc:
            data = utils.make_crc_adapter_async(data)

        logger.debug(
            f"Start to put object with signed url, bucket: {self.bucket_name}, sign_url: {sign_url}, headers: {headers}"
        )

        resp = await self._do_url("PUT", sign_url, data=data, headers=headers)
        logger.debug(f"Put object with url done, req_id: {resp.request_id}, status_code: {resp.status}")
        result = PutObjectResult(resp)

        if self.enable_crc and result.crc is not None:
            utils.check_crc("put object", data.crc, result.crc, result.request_id)

        return result

    async def put_object_with_url_from_file(self, sign_url, filename, headers=None, progress_callback=None):
        """使用加签的url上传本地文件到oss

        :param sign_url: 加签的url
        :param filename: 本地文件路径
        :param headers: 用户指定的HTTP头部。可以指定Content-Type、Content-MD5、x-oss-meta-开头的头部等，必须和签名时保持一致
        :param progress_callback: 用户指定的进度回调函数。参考 :ref:`progress_callback`
        :return:
        """
        logger.debug(
            f"Put object from file with signed url, bucket: {self.bucket_name}, sign_url: {sign_url}, file path: {filename}"
        )
        with open(to_unicode(filename), "rb") as f:
            return await self.put_object_with_url(sign_url, f, headers=headers, progress_callback=progress_callback)

    async def append_object(self, key, position, data, headers=None, progress_callback=None, init_crc=None):
        """追加上传一个文件。

        :param str key: 新的文件名，或已经存在的可追加文件名
        :param int position: 追加上传一个新的文件， `position` 设为0；追加一个已经存在的可追加文件， `position` 设为文件的当前长度。
            `position` 可以从上次追加的结果 `AppendObjectResult.next_position` 中获得。

        :param data: 用户数据
        :type data: str、bytes、file-like object或可迭代对象

        :param headers: 用户指定的HTTP头部。可以指定Content-Type、Content-MD5、x-oss-开头的头部等
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :param progress_callback: 用户指定的进度回调函数。参考 :ref:`progress_callback`

        :return: :class:`AppendObjectResult <oss2.models.AppendObjectResult>`

        :raises: 如果 `position` 和当前文件长度不一致，抛出 :class:`PositionNotEqualToLength <oss2.exceptions.PositionNotEqualToLength>` ；
                 如果当前文件不是可追加类型，抛出 :class:`ObjectNotAppendable <oss2.exceptions.ObjectNotAppendable>` ；
                 还会抛出其他一些异常
        """
        headers = utils.set_content_type(http.Headers(headers), key)

        if progress_callback:
            data = utils.make_progress_adapter_async(data, progress_callback)

        if self.enable_crc and init_crc is not None:
            data = utils.make_crc_adapter_async(data, init_crc)

        logger.debug(
            f"Start to append object, bucket: {self.bucket_name}, key: {key}, headers: {headers}, position: {position}"
        )
        resp = await self.__do_object(
            "POST", key, data=data, headers=headers, params={"append": "", "position": str(position)}
        )
        logger.debug(f"Append object done, req_id: {resp.request_id}, statu_code: {resp.status}")
        result = AppendObjectResult(resp)

        if self.enable_crc and result.crc is not None and init_crc is not None:
            utils.check_crc("append object", data.crc, result.crc, result.request_id)

        return result

    async def get_object(self, key, byte_range=None, headers=None, progress_callback=None, process=None, params=None):
        """下载一个文件。

        用法 ::

            >>> result = bucket.get_object('readme.txt')
            >>> print(result.read())
            'hello world'

        :param key: 文件名
        :param byte_range: 指定下载范围。参见 :ref:`byte_range`

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :param progress_callback: 用户指定的进度回调函数。参考 :ref:`progress_callback`

        :param process: oss文件处理，如图像服务等。指定后process，返回的内容为处理后的文件。

        :param params: http 请求的查询字符串参数
        :type params: dict

        :return: file-like object

        :raises: 如果文件不存在，则抛出 :class:`NoSuchKey <oss2.exceptions.NoSuchKey>` ；还可能抛出其他异常
        """
        headers = http.Headers(headers)

        range_string = _make_range_string(byte_range)
        if range_string:
            headers["range"] = range_string

        params = {} if params is None else params
        if process:
            params.update({AsyncBucket.PROCESS: process})

        logger.debug(
            f"Start to get object, bucket: {self.bucket_name}, key: {key}, range: {range_string}, headers: {headers}, params: {params}"
        )
        resp = await self.__do_object("GET", key, headers=headers, params=params)
        logger.debug(f"Get object done, req_id: {resp.request_id}, status_code: {resp.status}")

        return GetObjectResult(resp, progress_callback, self.enable_crc)

    async def select_object(self, key, sql, progress_callback=None, select_params=None, byte_range=None, headers=None):
        """Select一个文件内容，支持(Csv,Json Doc,Json Lines及其GZIP压缩文件).

        用法 ::
        对于Csv:
            >>> result = bucket.select_object('access.log', 'select * from ossobject where _4 > 40')
            >>> print(result.read())
            'hello world'
        对于Json Doc: { contacts:[{"firstName":"abc", "lastName":"def"},{"firstName":"abc1", "lastName":"def1"}]}
            >>> result = bucket.select_object('sample.json', 'select s.firstName, s.lastName from ossobject.contacts[*] s', select_params = {"Json_Type":"DOCUMENT"})

        对于Json Lines: {"firstName":"abc", "lastName":"def"},{"firstName":"abc1", "lastName":"def1"}
            >>> result = bucket.select_object('sample.json', 'select s.firstName, s.lastName from ossobject s', select_params = {"Json_Type":"LINES"})

        :param key: 文件名
        :param sql: sql statement
        :param select_params: select参数集合,对于Json文件必须制定Json_Type类型。参见 :ref:`select_params`

        :param progress_callback: 用户指定的进度回调函数。参考 :ref:`progress_callback`
        :param byte_range: select content of specific range。可以设置Bytes header指定select csv时的文件起始offset和长度。

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: file-like object

        :raises: 如果文件不存在，则抛出 :class:`NoSuchKey <oss2.exceptions.NoSuchKey>` ；还可能抛出其他异常
        """
        range_select = False
        headers = http.Headers(headers)
        range_string = _make_range_string(byte_range)
        if range_string:
            headers["range"] = range_string
            range_select = True

        if range_select and (
            select_params is None
            or (
                SelectParameters.AllowQuotedRecordDelimiter not in select_params
                or str(select_params[SelectParameters.AllowQuotedRecordDelimiter]).lower() != "false"
            )
        ):
            raise ClientError(
                '"AllowQuotedRecordDelimiter" must be specified in select_params as False when "Range" is specified in header.'
            )

        body = xml_utils.to_select_object(sql, select_params)
        params = {"x-oss-process": "csv/select"}
        if select_params is not None and SelectParameters.Json_Type in select_params:
            params["x-oss-process"] = "json/select"

        self.timeout = 3600
        resp = await self.__do_object("POST", key, data=body, headers=headers, params=params)
        crc_enabled = False
        if select_params is not None and SelectParameters.EnablePayloadCrc in select_params:
            if str(select_params[SelectParameters.EnablePayloadCrc]).lower() == "true":
                crc_enabled = True
        return SelectObjectResult(resp, progress_callback, crc_enabled)

    async def get_object_to_file(
        self, key, filename, byte_range=None, headers=None, progress_callback=None, process=None, params=None
    ):
        """下载一个文件到本地文件。

        :param key: 文件名
        :param filename: 本地文件名。要求父目录已经存在，且有写权限。
        :param byte_range: 指定下载范围。参见 :ref:`byte_range`

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :param progress_callback: 用户指定的进度回调函数。参考 :ref:`progress_callback`

        :param process: oss文件处理，如图像服务等。指定后process，返回的内容为处理后的文件。

        :param params: http 请求的查询字符串参数
        :type params: dict

        :return: 如果文件不存在，则抛出 :class:`NoSuchKey <oss2.exceptions.NoSuchKey>` ；还可能抛出其他异常
        """
        logger.debug(f"Start to get object to file, bucket: {self.bucket_name}, key: {key}, file path: {filename}")
        with open(to_unicode(filename), "wb") as f:
            result = await self.get_object(
                key,
                byte_range=byte_range,
                headers=headers,
                progress_callback=progress_callback,
                process=process,
                params=params,
            )

            if result.content_length is None:
                shutil.copyfileobj(result, f)
            else:
                utils.copyfileobj_and_verify(result, f, result.content_length, request_id=result.request_id)

            if self.enable_crc and byte_range is None:
                if (headers is None) or ("Accept-Encoding" not in headers) or (headers["Accept-Encoding"] != "gzip"):
                    utils.check_crc("get", result.client_crc, result.server_crc, result.request_id)

            return result

    async def get_object_with_url(self, sign_url, byte_range=None, headers=None, progress_callback=None):
        """使用加签的url下载文件

        :param sign_url: 加签的url
        :param byte_range: 指定下载范围。参见 :ref:`byte_range`

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict，必须和签名时保持一致

        :param progress_callback: 用户指定的进度回调函数。参考 :ref:`progress_callback`

        :return: file-like object

        :raises: 如果文件不存在，则抛出 :class:`NoSuchKey <oss2.exceptions.NoSuchKey>` ；还可能抛出其他异常
        """
        headers = http.Headers(headers)

        range_string = _make_range_string(byte_range)
        if range_string:
            headers["range"] = range_string

        logger.debug(
            f"Start to get object with url, bucket: {self.bucket_name}, sign_url: {sign_url}, range: {range_string}, headers: {headers}"
        )
        resp = await self._do_url("GET", sign_url, headers=headers)
        return GetObjectResult(resp, progress_callback, self.enable_crc)

    async def get_object_with_url_to_file(
        self, sign_url, filename, byte_range=None, headers=None, progress_callback=None
    ):
        """使用加签的url下载文件

        :param sign_url: 加签的url
        :param filename: 本地文件名。要求父目录已经存在，且有写权限。
        :param byte_range: 指定下载范围。参见 :ref:`byte_range`

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict，，必须和签名时保持一致

        :param progress_callback: 用户指定的进度回调函数。参考 :ref:`progress_callback`

        :return: file-like object

        :raises: 如果文件不存在，则抛出 :class:`NoSuchKey <oss2.exceptions.NoSuchKey>` ；还可能抛出其他异常
        """
        logger.debug(
            f"Start to get object with url, bucket: {self.bucket_name}, sign_url: {sign_url}, file path: {filename}, range: {byte_range}, headers: {headers}"
        )

        with open(to_unicode(filename), "wb") as f:
            result = await self.get_object_with_url(
                sign_url, byte_range=byte_range, headers=headers, progress_callback=progress_callback
            )
            if result.content_length is None:
                shutil.copyfileobj(result, f)
            else:
                utils.copyfileobj_and_verify(result, f, result.content_length, request_id=result.request_id)

            return result

    async def select_object_to_file(
        self, key, filename, sql, progress_callback=None, select_params=None, headers=None
    ):
        """Select一个文件的内容到本地文件

        :param key: OSS文件名
        :param filename: 本地文件名。其父亲目录已经存在且有写权限。

        :param progress_callback: 调用进度的callback。参考 :ref:`progress_callback`
        :param select_params: select参数集合。参见 :ref:`select_params`

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: 如果文件不存在, 抛出 :class:`NoSuchKey <oss2.exceptions.NoSuchKey>`
        """
        with open(to_unicode(filename), "wb") as f:
            result = await self.select_object(
                key, sql, progress_callback=progress_callback, select_params=select_params, headers=headers
            )

            for chunk in result:
                f.write(chunk)

            return result

    async def head_object(self, key, headers=None, params=None):
        """获取文件元信息。

        HTTP响应的头部包含了文件元信息，可以通过 `RequestResult` 的 `headers` 成员获得。
        用法 ::

            >>> result = bucket.head_object('readme.txt')
            >>> print(result.content_type)
            text/plain

        :param key: 文件名

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :param params: HTTP请求参数，传入versionId，获取指定版本Object元信息
        :type params: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`HeadObjectResult <oss2.models.HeadObjectResult>`

        :raises: 如果Bucket不存在或者Object不存在，则抛出 :class:`NotFound <oss2.exceptions.NotFound>`
        """
        logger.debug(f"Start to head object, bucket: {self.bucket_name}, key: {key}, headers: {headers}")

        resp = await self.__do_object("HEAD", key, headers=headers, params=params)

        logger.debug(f"Head object done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_dummy_result, HeadObjectResult)

    async def create_select_object_meta(self, key, select_meta_params=None, headers=None):
        """获取或创建CSV,JSON LINES 文件元信息。如果元信息存在，返回之；不然则创建后返回之

        HTTP响应的头部包含了文件元信息，可以通过 `RequestResult` 的 `headers` 成员获得。
        CSV文件用法 ::

            >>> select_meta_params = {  'FieldDelimiter': ',',
                                'RecordDelimiter': '\r\n',
                                'QuoteCharacter': '"',
                                'OverwriteIfExists' : 'false'}
            >>> result = bucket.create_select_object_meta('csv.txt', select_meta_params)
            >>> print(result.rows)

        JSON LINES文件用法 ::
            >>> select_meta_params = { 'Json_Type':'LINES', 'OverwriteIfExists':'False'}
            >>> result = bucket.create_select_object_meta('jsonlines.json', select_meta_params)
        :param key: 文件名
        :param select_meta_params: 参数词典，可以是dict，参见ref:`csv_meta_params`

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`GetSelectObjectMetaResult <oss2.models.HeadObjectResult>`.
          除了 rows 和splits 属性之外, 它也返回head object返回的其他属性。
          rows表示该文件的总记录数。
          splits表示该文件的总Split个数，一个Split包含若干条记录，每个Split的总字节数大致相当。用户可以以Split为单位进行分片查询。

        :raises: 如果Bucket不存在或者Object不存在，则抛出:class:`NotFound <oss2.exceptions.NotFound>`
        """
        headers = http.Headers(headers)

        body = xml_utils.to_get_select_object_meta(select_meta_params)
        params = {"x-oss-process": "csv/meta"}
        if select_meta_params is not None and "Json_Type" in select_meta_params:
            params["x-oss-process"] = "json/meta"

        self.timeout = 3600
        resp = await self.__do_object("POST", key, data=body, headers=headers, params=params)
        return GetSelectObjectMetaResult(resp)

    async def get_object_meta(self, key, params=None, headers=None):
        """获取文件基本元信息，包括该Object的ETag、Size（文件大小）、LastModified，并不返回其内容。

        HTTP响应的头部包含了文件基本元信息，可以通过 `GetObjectMetaResult` 的 `last_modified`，`content_length`,`etag` 成员获得。

        :param key: 文件名
        :param dict params: 请求参数

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`GetObjectMetaResult <oss2.models.GetObjectMetaResult>`

        :raises: 如果文件不存在，则抛出 :class:`NoSuchKey <oss2.exceptions.NoSuchKey>` ；还可能抛出其他异常
        """
        headers = http.Headers(headers)
        logger.debug(f"Start to get object metadata, bucket: {self.bucket_name}, key: {key}")

        if params is None:
            params = dict()

        if AsyncBucket.OBJECTMETA not in params:
            params[AsyncBucket.OBJECTMETA] = ""

        resp = await self.__do_object("HEAD", key, params=params, headers=headers)
        logger.debug(f"Get object metadata done, req_id: {resp.request_id}, status_code: {resp.status}")
        return GetObjectMetaResult(resp)

    async def object_exists(self, key, headers=None):
        """如果文件存在就返回True，否则返回False。如果Bucket不存在，或是发生其他错误，则抛出异常。"""
        #:param key: 文件名

        #:param headers: HTTP头部
        #:type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        # 如果我们用head_object来实现的话，由于HTTP HEAD请求没有响应体，只有响应头部，这样当发生404时，
        # 我们无法区分是NoSuchBucket还是NoSuchKey错误。
        #
        # 2.2.0之前的实现是通过get_object的if-modified-since头部，把date设为当前时间24小时后，这样如果文件存在，则会返回
        # 304 (NotModified)；不存在，则会返回NoSuchKey。get_object会受回源的影响，如果配置会404回源，get_object会判断错误。
        #
        # 目前的实现是通过get_object_meta判断文件是否存在。
        # get_object_meta 为200时，不会返回响应体，所以该接口把GET方法修改为HEAD 方式
        # 同时, 对于head 请求，服务端会通过x-oss-err 返回 错误响应信息,
        # 考虑到兼容之前的行为，增加exceptions.NotFound 异常 当作NoSuchKey

        logger.debug(f"Start to check if object exists, bucket: {self.bucket_name}, key: {key}")
        try:
            await self.get_object_meta(key, headers=headers)
        except exceptions.NoSuchKey:
            return False
        except exceptions.NoSuchBucket:
            raise
        except exceptions.NotFound:
            return False
        except:
            raise

        return True

    async def copy_object(self, source_bucket_name, source_key, target_key, headers=None, params=None):
        """拷贝一个文件到当前Bucket。

        :param str source_bucket_name: 源Bucket名
        :param str source_key: 源文件名
        :param str target_key: 目标文件名
        :param dict params: 请求参数

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`PutObjectResult <oss2.models.PutObjectResult>`
        """

        headers = http.Headers(headers)

        if params and AsyncBucket.VERSIONID in params:
            headers[OSS_COPY_OBJECT_SOURCE] = (
                "/" + source_bucket_name + "/" + quote(source_key, "") + "?versionId=" + params[AsyncBucket.VERSIONID]
            )
        else:
            headers[OSS_COPY_OBJECT_SOURCE] = "/" + source_bucket_name + "/" + quote(source_key, "")

        logger.debug(
            f"Start to copy object, source bucket: {source_bucket_name}, source key: {source_key}, bucket: {self.bucket_name}, key: {target_key}, headers: {headers}"
        )
        resp = await self.__do_object("PUT", target_key, headers=headers)
        logger.debug(f"Copy object done, req_id: {resp.request_id}, status_code: {resp.status}")

        return PutObjectResult(resp)

    async def update_object_meta(self, key, headers):
        """更改Object的元数据信息，包括Content-Type这类标准的HTTP头部，以及以x-oss-meta-开头的自定义元数据。

        用户可以通过 :func:`head_object` 获得元数据信息。

        :param str key: 文件名

        :param headers: HTTP头部，包含了元数据信息
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`RequestResult <oss2.models.RequestResults>`
        """

        if headers is not None:
            headers[OSS_METADATA_DIRECTIVE] = "REPLACE"

        logger.debug(f"Start to update object metadata, bucket: {self.bucket_name}, key: {key}")
        return await self.copy_object(self.bucket_name, key, key, headers=headers)

    async def delete_object(self, key, params=None, headers=None):
        """删除一个文件。

        :param str key: 文件名
        :param params: 请求参数

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """

        headers = http.Headers(headers)

        logger.info(f"Start to delete object, bucket: {self.bucket_name}, key: {key}")
        resp = await self.__do_object("DELETE", key, params=params, headers=headers)
        logger.debug(f"Delete object done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def restore_object(self, key, params=None, headers=None, input=None):
        """restore an object
            如果是第一次针对该object调用接口，返回RequestResult.status = 202；
            如果已经成功调用过restore接口，且服务端仍处于解冻中，抛异常RestoreAlreadyInProgress(status=409)
            如果已经成功调用过restore接口，且服务端解冻已经完成，再次调用时返回RequestResult.status = 200，且会将object的可下载时间延长一天，最多延长7天。
            如果object不存在，则抛异常NoSuchKey(status=404)；
            对非Archive类型的Object提交restore，则抛异常OperationNotSupported(status=400)

            也可以通过调用head_object接口来获取meta信息来判断是否可以restore与restore的状态
            代码示例::
            >>> meta = bucket.head_object(key)
            >>> if meta.resp.headers['x-oss-storage-class'] == oss2.BUCKET_STORAGE_CLASS_ARCHIVE:
            >>>     bucket.restore_object(key)
            >>>         while True:
            >>>             meta = bucket.head_object(key)
            >>>             if meta.resp.headers['x-oss-restore'] == 'ongoing-request="true"':
            >>>                 time.sleep(5)
            >>>             else:
            >>>                 break
        :param str key: object name
        :param params: 请求参数

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :param input: 解冻配置。
        :type input: class:`RestoreConfiguration <oss2.models.RestoreConfiguration>`

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        headers = http.Headers(headers)
        logger.debug(f"Start to restore object, bucket: {self.bucket_name}, key: {key}")

        if params is None:
            params = dict()

        if AsyncBucket.RESTORE not in params:
            params[AsyncBucket.RESTORE] = ""

        data = self.__convert_data(RestoreConfiguration, xml_utils.to_put_restore_config, input)

        resp = await self.__do_object("POST", key, params=params, headers=headers, data=data)
        logger.debug(f"Restore object done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def put_object_acl(self, key, permission, params=None, headers=None):
        """设置文件的ACL。

        :param str key: 文件名
        :param str permission: 可以是oss2.OBJECT_ACL_DEFAULT、oss2.OBJECT_ACL_PRIVATE、oss2.OBJECT_ACL_PUBLIC_READ或
            oss2.OBJECT_ACL_PUBLIC_READ_WRITE。
        :param dict params: 请求参数

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to put object acl, bucket: {self.bucket_name}, key: {key}, acl: {permission}")

        headers = http.Headers(headers)
        headers[OSS_OBJECT_ACL] = permission

        if params is None:
            params = dict()

        if AsyncBucket.ACL not in params:
            params[AsyncBucket.ACL] = ""

        resp = await self.__do_object("PUT", key, params=params, headers=headers)
        logger.debug(f"Put object acl done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_object_acl(self, key, params=None, headers=None):
        """获取文件的ACL。

        :param key: 文件名
        :param params: 请求参数

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`GetObjectAclResult <oss2.models.GetObjectAclResult>`
        """
        logger.debug(f"Start to get object acl, bucket: {self.bucket_name}, key: {key}")
        headers = http.Headers(headers)

        if params is None:
            params = dict()

        if AsyncBucket.ACL not in params:
            params[AsyncBucket.ACL] = ""

        resp = await self.__do_object("GET", key, params=params, headers=headers)
        logger.debug(f"Get object acl done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_object_acl, GetObjectAclResult)

    async def batch_delete_objects(self, key_list, headers=None):
        """批量删除文件。待删除文件列表不能为空。

        :param key_list: 文件名列表，不能为空。
        :type key_list: list of str

        :param headers: HTTP头部

        :return: :class:`BatchDeleteObjectsResult <oss2.models.BatchDeleteObjectsResult>`
        """
        if not key_list:
            raise ClientError("key_list should not be empty")

        logger.debug(f"Start to delete objects, bucket: {self.bucket_name}, keys: {key_list}")

        data = xml_utils.to_batch_delete_objects_request(key_list, False)

        headers = http.Headers(headers)
        headers["Content-MD5"] = utils.content_md5(data)

        resp = await self.__do_bucket(
            "POST", data=data, params={"delete": "", "encoding-type": "url"}, headers=headers
        )
        logger.debug(f"Delete objects done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_batch_delete_objects, BatchDeleteObjectsResult)

    async def delete_object_versions(self, keylist_versions, headers=None):
        """批量删除带版本文件。待删除文件列表不能为空。

        :param key_list_with_version: 带版本的文件名列表，不能为空。（如果传入，则不能为空）
        :type key_list: list of BatchDeleteObjectsList

        :param headers: HTTP头部

        :return: :class:`BatchDeleteObjectsResult <oss2.models.BatchDeleteObjectsResult>`
        """
        if not keylist_versions:
            raise ClientError("keylist_versions should not be empty")

        logger.debug(f"Start to delete object versions, bucket: {self.bucket_name}")

        data = xml_utils.to_batch_delete_objects_version_request(keylist_versions, False)

        headers = http.Headers(headers)
        headers["Content-MD5"] = utils.content_md5(data)

        resp = await self.__do_bucket(
            "POST", data=data, params={"delete": "", "encoding-type": "url"}, headers=headers
        )
        logger.debug(f"Delete object versions done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_batch_delete_objects, BatchDeleteObjectsResult)

    async def init_multipart_upload(self, key, headers=None, params=None):
        """初始化分片上传。

        返回值中的 `upload_id` 以及Bucket名和Object名三元组唯一对应了此次分片上传事件。

        :param str key: 待上传的文件名

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`InitMultipartUploadResult <oss2.models.InitMultipartUploadResult>`
        """
        headers = utils.set_content_type(http.Headers(headers), key)

        if params is None:
            tmp_params = dict()
        else:
            tmp_params = params.copy()

        tmp_params["uploads"] = ""
        logger.debug(
            f"Start to init multipart upload, bucket: {self.bucket_name}, keys: {key}, headers: {headers}, params: {tmp_params}"
        )
        resp = await self.__do_object("POST", key, params=tmp_params, headers=headers)
        logger.debug(f"Init multipart upload done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_init_multipart_upload, InitMultipartUploadResult)

    async def upload_part(self, key, upload_id, part_number, data, progress_callback=None, headers=None):
        """上传一个分片。

        :param str key: 待上传文件名，这个文件名要和 :func:`init_multipart_upload` 的文件名一致。
        :param str upload_id: 分片上传ID
        :param int part_number: 分片号，最小值是1.
        :param data: 待上传数据。
        :param progress_callback: 用户指定进度回调函数。可以用来实现进度条等功能。参考 :ref:`progress_callback` 。

        :param headers: 用户指定的HTTP头部。可以指定Content-MD5头部等
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`PutObjectResult <oss2.models.PutObjectResult>`
        """
        headers = http.Headers(headers)

        if progress_callback:
            data = utils.make_progress_adapter_async(data, progress_callback)

        if self.enable_crc:
            data = utils.make_crc_adapter_async(data)

        logger.debug(
            f"Start to upload multipart, bucket: {self.bucket_name}, key: {key}, upload_id: {upload_id}, part_number: {part_number}, headers: {headers}"
        )
        resp = await self.__do_object(
            "PUT", key, params={"uploadId": upload_id, "partNumber": str(part_number)}, headers=headers, data=data
        )
        logger.debug(f"Upload multipart done, req_id: {resp.request_id}, status_code: {resp.status}")
        result = PutObjectResult(resp)

        if self.enable_crc and result.crc is not None:
            utils.check_crc("upload part", data.crc, result.crc, result.request_id)

        return result

    async def complete_multipart_upload(self, key, upload_id, parts, headers=None):
        """完成分片上传，创建文件。

        :param str key: 待上传的文件名，这个文件名要和 :func:`init_multipart_upload` 的文件名一致。
        :param str upload_id: 分片上传ID

        :param parts: PartInfo列表。PartInfo中的part_number和etag是必填项。其中的etag可以从 :func:`upload_part` 的返回值中得到。
        :type parts: list of `PartInfo <oss2.models.PartInfo>`

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`PutObjectResult <oss2.models.PutObjectResult>`
        """
        headers = http.Headers(headers)

        data = None
        if parts is not None:
            parts = sorted(parts, key=lambda p: p.part_number)
            data = xml_utils.to_complete_upload_request(parts)

        logger.debug(
            f"Start to complete multipart upload, bucket: {self.bucket_name}, key: {key}, upload_id: {upload_id}, parts: {data}"
        )

        resp = await self.__do_object("POST", key, params={"uploadId": upload_id}, data=data, headers=headers)
        logger.debug(f"Complete multipart upload done, req_id: {resp.request_id}, status_code: {resp.status}")

        result = PutObjectResult(resp)

        if self.enable_crc and parts is not None:
            object_crc = utils.calc_obj_crc_from_parts(parts)
            utils.check_crc("multipart upload", object_crc, result.crc, result.request_id)

        return result

    async def abort_multipart_upload(self, key, upload_id, headers=None):
        """取消分片上传。

        :param str key: 待上传的文件名，这个文件名要和 :func:`init_multipart_upload` 的文件名一致。
        :param str upload_id: 分片上传ID

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """

        logger.debug(
            f"Start to abort multipart upload, bucket: {self.bucket_name}, key: {key}, upload_id: {upload_id}"
        )

        headers = http.Headers(headers)

        resp = await self.__do_object("DELETE", key, params={"uploadId": upload_id}, headers=headers)
        logger.debug(f"Abort multipart done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def list_multipart_uploads(
        self, prefix="", delimiter="", key_marker="", upload_id_marker="", max_uploads=1000, headers=None
    ):
        """罗列正在进行中的分片上传。支持分页。

        :param str prefix: 只罗列匹配该前缀的文件的分片上传
        :param str delimiter: 目录分割符
        :param str key_marker: 文件名分页符。第一次调用可以不传，后续设为返回值中的 `next_key_marker`
        :param str upload_id_marker: 分片ID分页符。第一次调用可以不传，后续设为返回值中的 `next_upload_id_marker`
        :param int max_uploads: 一次罗列最多能够返回的条目数

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`ListMultipartUploadsResult <oss2.models.ListMultipartUploadsResult>`
        """
        logger.debug(
            f"Start to list multipart uploads, bucket: {self.bucket_name}, prefix: {prefix}, delimiter: {delimiter}, key_marker: {key_marker}, "
            f"upload_id_marker: {upload_id_marker}, max_uploads: {max_uploads}"
        )

        headers = http.Headers(headers)

        resp = await self.__do_bucket(
            "GET",
            params={
                "uploads": "",
                "prefix": prefix,
                "delimiter": delimiter,
                "key-marker": key_marker,
                "upload-id-marker": upload_id_marker,
                "max-uploads": str(max_uploads),
                "encoding-type": "url",
            },
            headers=headers,
        )
        logger.debug(f"List multipart uploads done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_list_multipart_uploads, ListMultipartUploadsResult)

    async def upload_part_copy(
        self,
        source_bucket_name,
        source_key,
        byte_range,
        target_key,
        target_upload_id,
        target_part_number,
        headers=None,
        params=None,
    ):
        """分片拷贝。把一个已有文件的一部分或整体拷贝成目标文件的一个分片。
        :source_bucket_name: 源文件所在bucket的名称
        :source_key:源文件名称
        :param byte_range: 指定待拷贝内容在源文件里的范围。参见 :ref:`byte_range`
        :target_key: 目的文件的名称
        :target_upload_id: 目的文件的uploadid
        :target_part_number: 目的文件的分片号
        :param params: 请求参数

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`PutObjectResult <oss2.models.PutObjectResult>`
        """
        headers = http.Headers(headers)

        if params and AsyncBucket.VERSIONID in params:
            headers[OSS_COPY_OBJECT_SOURCE] = (
                "/" + source_bucket_name + "/" + quote(source_key, "") + "?versionId=" + params[AsyncBucket.VERSIONID]
            )
        else:
            headers[OSS_COPY_OBJECT_SOURCE] = "/" + source_bucket_name + "/" + quote(source_key, "")

        range_string = _make_range_string(byte_range)
        if range_string:
            headers[OSS_COPY_OBJECT_SOURCE_RANGE] = range_string

        logger.debug(
            f"Start to upload part copy, source bucket: {source_bucket_name}, source key: {source_key}, bucket: {self.bucket_name}, key: {target_key}, range: {byte_range}, upload id: {target_upload_id}, part_number: {target_part_number}, headers: {headers}"
        )

        if params is None:
            params = dict()

        params["uploadId"] = target_upload_id
        params["partNumber"] = str(target_part_number)

        resp = await self.__do_object("PUT", target_key, params=params, headers=headers)
        logger.debug(f"Upload part copy done, req_id: {resp.request_id}, status_code: {resp.status}")

        return PutObjectResult(resp)

    async def list_parts(self, key, upload_id, marker="", max_parts=1000, headers=None):
        """列举已经上传的分片。支持分页。

        :param headers: HTTP头部
        :param str key: 文件名
        :param str upload_id: 分片上传ID
        :param str marker: 分页符
        :param int max_parts: 一次最多罗列多少分片

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`ListPartsResult <oss2.models.ListPartsResult>`
        """
        logger.debug(
            f"Start to list parts, bucket: {self.bucket_name}, key: {key}, upload_id: {upload_id}, marker: {marker}, max_parts: {max_parts}"
        )

        headers = http.Headers(headers)

        resp = await self.__do_object(
            "GET",
            key,
            params={"uploadId": upload_id, "part-number-marker": marker, "max-parts": str(max_parts)},
            headers=headers,
        )
        logger.debug(f"List parts done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_list_parts, ListPartsResult)

    async def put_symlink(self, target_key, symlink_key, headers=None):
        """创建Symlink。

        :param str target_key: 目标文件，目标文件不能为符号连接
        :param str symlink_key: 符号连接类文件，其实质是一个特殊的文件，数据指向目标文件

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        headers = http.Headers(headers)
        headers[OSS_SYMLINK_TARGET] = quote(target_key, "")

        logger.debug(
            f"Start to put symlink, bucket: {self.bucket_name}, target_key: {target_key}, symlink_key: {symlink_key}, headers: {headers}"
        )
        resp = await self.__do_object("PUT", symlink_key, headers=headers, params={AsyncBucket.SYMLINK: ""})
        logger.debug(f"Put symlink done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_symlink(self, symlink_key, params=None, headers=None):
        """获取符号连接文件的目标文件。

        :param str symlink_key: 符号连接类文件
        :param dict params: 请求参数

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`GetSymlinkResult <oss2.models.GetSymlinkResult>`

        :raises: 如果文件的符号链接不存在，则抛出 :class:`NoSuchKey <oss2.exceptions.NoSuchKey>` ；还可能抛出其他异常
        """
        logger.debug(f"Start to get symlink, bucket: {self.bucket_name}, symlink_key: {symlink_key}")

        headers = http.Headers(headers)

        if params is None:
            params = dict()

        if AsyncBucket.SYMLINK not in params:
            params[AsyncBucket.SYMLINK] = ""

        resp = await self.__do_object("GET", symlink_key, params=params, headers=headers)
        logger.debug(f"Get symlink done, req_id: {resp.request_id}, status_code: {resp.status}")
        return GetSymlinkResult(resp)

    async def create_bucket(self, permission=None, input=None, headers=None):
        """创建新的Bucket。

        :param str permission: 指定Bucket的ACL。可以是oss2.BUCKET_ACL_PRIVATE（推荐、缺省）、oss2.BUCKET_ACL_PUBLIC_READ或是
            oss2.BUCKET_ACL_PUBLIC_READ_WRITE。

        :param input: :class:`BucketCreateConfig <oss2.models.BucketCreateConfig>` object
        """
        headers = http.Headers(headers)
        if permission:
            headers[OSS_CANNED_ACL] = permission

        data = self.__convert_data(BucketCreateConfig, xml_utils.to_put_bucket_config, input)
        logger.debug(f"Start to create bucket, bucket: {self.bucket_name}, permission: {permission}, config: {data}")
        resp = await self.__do_bucket("PUT", headers=headers, data=data)
        logger.debug(f"Create bucket done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def delete_bucket(self):
        """删除一个Bucket。只有没有任何文件，也没有任何未完成的分片上传的Bucket才能被删除。

        :return: :class:`RequestResult <oss2.models.RequestResult>`

        ":raises: 如果试图删除一个非空Bucket，则抛出 :class:`BucketNotEmpty <oss2.exceptions.BucketNotEmpty>`
        """
        logger.info(f"Start to delete bucket, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("DELETE")
        logger.debug(f"Delete bucket done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def put_bucket_acl(self, permission):
        """设置Bucket的ACL。

        :param str permission: 新的ACL，可以是oss2.BUCKET_ACL_PRIVATE、oss2.BUCKET_ACL_PUBLIC_READ或
            oss2.BUCKET_ACL_PUBLIC_READ_WRITE
        """
        logger.debug(f"Start to put bucket acl, bucket: {self.bucket_name}, acl: {permission}")
        resp = await self.__do_bucket("PUT", headers={OSS_CANNED_ACL: permission}, params={AsyncBucket.ACL: ""})
        logger.debug(f"Put bucket acl done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_bucket_acl(self):
        """获取Bucket的ACL。

        :return: :class:`GetBucketAclResult <oss2.models.GetBucketAclResult>`
        """
        logger.debug(f"Start to get bucket acl, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.ACL: ""})
        logger.debug(f"Get bucket acl done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_bucket_acl, GetBucketAclResult)

    async def put_bucket_cors(self, input):
        """设置Bucket的CORS。

        :param input: :class:`BucketCors <oss2.models.BucketCors>` 对象或其他
        """
        data = self.__convert_data(BucketCors, xml_utils.to_put_bucket_cors, input)
        logger.debug(f"Start to put bucket cors, bucket: {self.bucket_name}, cors: {data}")
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.CORS: ""})
        logger.debug(f"Put bucket cors done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_bucket_cors(self):
        """获取Bucket的CORS配置。

        :return: :class:`GetBucketCorsResult <oss2.models.GetBucketCorsResult>`
        """
        logger.debug(f"Start to get bucket CORS, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.CORS: ""})
        logger.debug(f"Get bucket CORS done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_bucket_cors, GetBucketCorsResult)

    async def delete_bucket_cors(self):
        """删除Bucket的CORS配置。"""
        logger.debug(f"Start to delete bucket CORS, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("DELETE", params={AsyncBucket.CORS: ""})
        logger.debug(f"Delete bucket CORS done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def put_bucket_lifecycle(self, input, headers=None):
        """设置生命周期管理的配置。

        :param input: :class:`BucketLifecycle <oss2.models.BucketLifecycle>` 对象或其他
        """
        headers = http.Headers(headers)
        data = self.__convert_data(BucketLifecycle, xml_utils.to_put_bucket_lifecycle, input)
        logger.debug(f"Start to put bucket lifecycle, bucket: {self.bucket_name}, lifecycle: {data}")
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.LIFECYCLE: ""}, headers=headers)
        logger.debug(f"Put bucket lifecycle done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_bucket_lifecycle(self):
        """获取生命周期管理配置。

        :return: :class:`GetBucketLifecycleResult <oss2.models.GetBucketLifecycleResult>`

        :raises: 如果没有设置Lifecycle，则抛出 :class:`NoSuchLifecycle <oss2.exceptions.NoSuchLifecycle>`
        """
        logger.debug(f"Start to get bucket lifecycle, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.LIFECYCLE: ""})
        logger.debug(f"Get bucket lifecycle done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_bucket_lifecycle, GetBucketLifecycleResult)

    async def delete_bucket_lifecycle(self):
        """删除生命周期管理配置。如果Lifecycle没有设置，也返回成功。"""
        logger.debug(f"Start to delete bucket lifecycle, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("DELETE", params={AsyncBucket.LIFECYCLE: ""})
        logger.debug(f"Delete bucket lifecycle done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_bucket_location(self):
        """获取Bucket的数据中心。

        :return: :class:`GetBucketLocationResult <oss2.models.GetBucketLocationResult>`
        """
        logger.debug(f"Start to get bucket location, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.LOCATION: ""})
        logger.debug(f"Get bucket location done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_bucket_location, GetBucketLocationResult)

    async def put_bucket_logging(self, input):
        """设置Bucket的访问日志功能。

        :param input: :class:`BucketLogging <oss2.models.BucketLogging>` 对象或其他
        """
        data = self.__convert_data(BucketLogging, xml_utils.to_put_bucket_logging, input)
        logger.debug(f"Start to put bucket logging, bucket: {self.bucket_name}, logging: {data}")
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.LOGGING: ""})
        logger.debug(f"Put bucket logging done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_bucket_logging(self):
        """获取Bucket的访问日志功能配置。

        :return: :class:`GetBucketLoggingResult <oss2.models.GetBucketLoggingResult>`
        """
        logger.debug(f"Start to get bucket logging, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.LOGGING: ""})
        logger.debug(f"Get bucket logging done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_bucket_logging, GetBucketLoggingResult)

    async def delete_bucket_logging(self):
        """关闭Bucket的访问日志功能。"""
        logger.debug(f"Start to delete bucket loggging, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("DELETE", params={AsyncBucket.LOGGING: ""})
        logger.debug(f"Delete bucket lifecycle done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def put_bucket_referer(self, input):
        """为Bucket设置防盗链。

        :param input: :class:`BucketReferer <oss2.models.BucketReferer>` 对象或其他
        """
        data = self.__convert_data(BucketReferer, xml_utils.to_put_bucket_referer, input)
        logger.debug(f"Start to put bucket referer, bucket: {self.bucket_name}, referer: {data}")
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.REFERER: ""})
        logger.debug(f"Put bucket referer done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_bucket_referer(self):
        """获取Bucket的防盗链配置。

        :return: :class:`GetBucketRefererResult <oss2.models.GetBucketRefererResult>`
        """
        logger.debug(f"Start to get bucket referer, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.REFERER: ""})
        logger.debug(f"Get bucket referer done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_bucket_referer, GetBucketRefererResult)

    async def get_bucket_stat(self):
        """查看Bucket的状态，目前包括bucket大小，bucket的object数量，bucket正在上传的Multipart Upload事件个数等。

        :return: :class:`GetBucketStatResult <oss2.models.GetBucketStatResult>`
        """
        logger.debug(f"Start to get bucket stat, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.STAT: ""})
        logger.debug(f"Get bucket stat done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_bucket_stat, GetBucketStatResult)

    async def get_bucket_info(self):
        """获取bucket相关信息，如创建时间，访问Endpoint，Owner与ACL等。

        :return: :class:`GetBucketInfoResult <oss2.models.GetBucketInfoResult>`
        """
        logger.debug(f"Start to get bucket info, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.BUCKET_INFO: ""})
        logger.debug(f"Get bucket info done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_bucket_info, GetBucketInfoResult)

    async def put_bucket_website(self, input):
        """为Bucket配置静态网站托管功能。

        :param input: :class:`BucketWebsite <oss2.models.BucketWebsite>`
        """
        data = self.__convert_data(BucketWebsite, xml_utils.to_put_bucket_website, input)

        headers = http.Headers()
        headers["Content-MD5"] = utils.content_md5(data)

        logger.debug(f"Start to put bucket website, bucket: {self.bucket_name}, website: {data}")
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.WEBSITE: ""}, headers=headers)
        logger.debug(f"Put bucket website done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_bucket_website(self):
        """获取Bucket的静态网站托管配置。

        :return: :class:`GetBucketWebsiteResult <oss2.models.GetBucketWebsiteResult>`

        :raises: 如果没有设置静态网站托管，那么就抛出 :class:`NoSuchWebsite <oss2.exceptions.NoSuchWebsite>`
        """

        logger.debug(f"Start to get bucket website, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.WEBSITE: ""})
        logger.debug(f"Get bucket website done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_get_bucket_website, GetBucketWebsiteResult)

    async def delete_bucket_website(self):
        """关闭Bucket的静态网站托管功能。"""
        logger.debug(f"Start to delete bucket website, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("DELETE", params={AsyncBucket.WEBSITE: ""})
        logger.debug(f"Delete bucket website done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def create_live_channel(self, channel_name, input):
        """创建推流直播频道

        :param str channel_name: 要创建的live channel的名称
        :param input: LiveChannelInfo类型，包含了live channel中的描述信息

        :return: :class:`CreateLiveChannelResult <oss2.models.CreateLiveChannelResult>`
        """
        data = self.__convert_data(LiveChannelInfo, xml_utils.to_create_live_channel, input)
        logger.debug(
            f"Start to create live-channel, bucket: {self.bucket_name}, channel_name: {channel_name}, info: {data}"
        )
        resp = await self.__do_object("PUT", channel_name, data=data, params={AsyncBucket.LIVE: ""})
        logger.debug(f"Create live-channel done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_create_live_channel, CreateLiveChannelResult)

    async def delete_live_channel(self, channel_name):
        """删除推流直播频道

        :param str channel_name: 要删除的live channel的名称
        """
        logger.debug(f"Start to delete live-channel, bucket: {self.bucket_name}, live_channel: {channel_name}")
        resp = await self.__do_object("DELETE", channel_name, params={AsyncBucket.LIVE: ""})
        logger.debug(f"Delete live-channel done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_live_channel(self, channel_name):
        """获取直播频道配置

        :param str channel_name: 要获取的live channel的名称

        :return: :class:`GetLiveChannelResult <oss2.models.GetLiveChannelResult>`
        """
        logger.debug(f"Start to get live-channel info: bucket: {self.bucket_name}, live_channel: {channel_name}")
        resp = await self.__do_object("GET", channel_name, params={AsyncBucket.LIVE: ""})
        logger.debug(f"Get live-channel done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_live_channel, GetLiveChannelResult)

    async def list_live_channel(self, prefix="", marker="", max_keys=100):
        """列举出Bucket下所有符合条件的live channel

        param: str prefix: list时channel_id的公共前缀
        param: str marker: list时指定的起始标记
        param: int max_keys: 本次list返回live channel的最大个数

        return: :class:`ListLiveChannelResult <oss2.models.ListLiveChannelResult>`
        """
        logger.debug(
            f"Start to list live-channels, bucket: {self.bucket_name}, prefix: {prefix}, marker: {marker}, max_keys: {max_keys}"
        )
        resp = await self.__do_bucket(
            "GET", params={AsyncBucket.LIVE: "", "prefix": prefix, "marker": marker, "max-keys": str(max_keys)}
        )
        logger.debug(f"List live-channel done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_list_live_channel, ListLiveChannelResult)

    async def get_live_channel_stat(self, channel_name):
        """获取live channel当前推流的状态

        param str channel_name: 要获取推流状态的live channel的名称

        return: :class:`GetLiveChannelStatResult <oss2.models.GetLiveChannelStatResult>`
        """
        logger.debug(f"Start to get live-channel stat, bucket: {self.bucket_name}, channel_name: {channel_name}")
        resp = await self.__do_object("GET", channel_name, params={AsyncBucket.LIVE: "", AsyncBucket.COMP: "stat"})
        logger.debug(f"Get live-channel stat done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_live_channel_stat, GetLiveChannelStatResult)

    async def put_live_channel_status(self, channel_name, status):
        """更改live channel的status，仅能在“enabled”和“disabled”两种状态中更改

        param str channel_name: 要更改status的live channel的名称
        param str status: live channel的目标status
        """
        logger.debug(
            f"Start to put live-channel status, bucket: {self.bucket_name}, channel_name: {channel_name}, status: {status}"
        )
        resp = await self.__do_object("PUT", channel_name, params={AsyncBucket.LIVE: "", AsyncBucket.STATUS: status})
        logger.debug(f"Put live-channel status done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_live_channel_history(self, channel_name):
        """获取live channel中最近的最多十次的推流记录，记录中包含推流的起止时间和远端的地址

        param str channel_name: 要获取最近推流记录的live channel的名称

        return: :class:`GetLiveChannelHistoryResult <oss2.models.GetLiveChannelHistoryResult>`
        """
        logger.debug(f"Start to get live-channel history, bucket: {self.bucket_name}, channel_name: {channel_name}")
        resp = await self.__do_object("GET", channel_name, params={AsyncBucket.LIVE: "", AsyncBucket.COMP: "history"})
        logger.debug(f"Get live-channel history done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_live_channel_history, GetLiveChannelHistoryResult)

    async def post_vod_playlist(self, channel_name, playlist_name, start_time=0, end_time=0):
        """根据指定的playlist name以及startTime和endTime生成一个点播的播放列表

        param str channel_name: 要生成点播列表的live channel的名称
        param str playlist_name: 要生成点播列表m3u8文件的名称
        param int start_time: 点播的起始时间，Unix Time格式，可以使用int(time.time())获取
        param int end_time: 点播的结束时间，Unix Time格式，可以使用int(time.time())获取
        """
        logger.debug(
            f"Start to post vod playlist, bucket: {self.bucket_name}, channel_name: {channel_name}, playlist_name: {playlist_name}, start_time: "
            f"{start_time}, end_time: {end_time}"
        )
        key = channel_name + "/" + playlist_name
        resp = await self.__do_object(
            "POST", key, params={AsyncBucket.VOD: "", "startTime": str(start_time), "endTime": str(end_time)}
        )
        logger.debug(f"Post vod playlist done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_vod_playlist(self, channel_name, start_time, end_time):
        """查看指定时间段内的播放列表

        param str channel_name: 要获取点播列表的live channel的名称
        param int start_time: 点播的起始时间，Unix Time格式，可以使用int(time.time())获取
        param int end_time: 点播的结束时间，Unix Time格式，可以使用int(time.time())获取
        """
        logger.debug(
            f"Start to get vod playlist, bucket: {self.bucket_name}, channel_name: {channel_name},  start_time: "
            f"{start_time}, end_time: {end_time}"
        )
        resp = await self.__do_object(
            "GET", channel_name, params={AsyncBucket.VOD: "", "startTime": str(start_time), "endTime": str(end_time)}
        )
        logger.debug(f"get vod playlist done, req_id: {resp.request_id}, status_code: {resp.status}")
        result = GetVodPlaylistResult(resp)
        return result

    async def process_object(self, key, process, headers=None):
        """处理图片的接口，支持包括调整大小，旋转，裁剪，水印，格式转换等，支持多种方式组合处理。

        :param str key: 处理的图片的对象名称
        :param str process: 处理的字符串，例如"image/resize,w_100|sys/saveas,o_dGVzdC5qcGc,b_dGVzdA"

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict
        """

        headers = http.Headers(headers)

        logger.debug(f"Start to process object, bucket: {self.bucket_name}, key: {key}, process: {process}")
        process_data = f"{AsyncBucket.PROCESS}={process}"
        resp = await self.__do_object(
            "POST", key, params={AsyncBucket.PROCESS: ""}, headers=headers, data=process_data
        )
        logger.debug(f"Process object done, req_id: {resp.request_id}, status_code: {resp.status}")
        return ProcessObjectResult(resp)

    async def put_object_tagging(self, key, tagging, headers=None, params=None):
        """

        :param str key: 上传tagging的对象名称，不能为空。

        :param tagging: tag 标签内容
        :type tagging: :class:`Tagging <oss2.models.Tagging>` 对象

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :param dict params: HTTP请求参数

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to put object tagging, bucket: {self.bucket_name}, key: {key}, tagging: {tagging}")

        if headers is not None:
            headers = http.Headers(headers)

        if params is None:
            params = dict()

        params[AsyncBucket.TAGGING] = ""

        data = self.__convert_data(Tagging, xml_utils.to_put_tagging, tagging)
        resp = await self.__do_object("PUT", key, data=data, params=params, headers=headers)

        return RequestResult(resp)

    async def get_object_tagging(self, key, params=None, headers=None):
        """
        :param str key: 要获取tagging的对象名称
        :param dict params: 请求参数

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`GetTaggingResult <oss2.models.GetTaggingResult>`
        """
        logger.debug(f"Start to get object tagging, bucket: {self.bucket_name}, key: {key}, params: {params}")

        headers = http.Headers(headers)

        if params is None:
            params = dict()

        params[AsyncBucket.TAGGING] = ""

        resp = await self.__do_object("GET", key, params=params, headers=headers)

        return self._parse_result(resp, xml_utils.parse_get_tagging, GetTaggingResult)

    async def delete_object_tagging(self, key, params=None, headers=None):
        """
        :param str key: 要删除tagging的对象名称
        :param dict params: 请求参数

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to delete object tagging, bucket: {self.bucket_name}, key: {key}")

        headers = http.Headers(headers)

        if params is None:
            params = dict()

        params[AsyncBucket.TAGGING] = ""

        resp = await self.__do_object("DELETE", key, params=params, headers=headers)

        logger.debug(f"Delete object tagging done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def put_bucket_encryption(self, rule):
        """设置bucket加密配置。

        :param rule: :class:` ServerSideEncryptionRule<oss2.models.ServerSideEncryptionRule>` 对象
        """
        data = self.__convert_data(ServerSideEncryptionRule, xml_utils.to_put_bucket_encryption, rule)

        logger.debug(f"Start to put bucket encryption, bucket: {self.bucket_name}, rule: {data}")
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.ENCRYPTION: ""})
        logger.debug(f"Put bucket encryption done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_bucket_encryption(self):
        """获取bucket加密配置。

        :return: :class:`GetServerSideEncryptionResult <oss2.models.GetServerSideEncryptionResult>`

        :raises: 如果没有设置Bucket encryption，则抛出 :class:`NoSuchServerSideEncryptionRule <oss2.exceptions.NoSuchServerSideEncryptionRule>`
        """
        logger.debug(f"Start to get bucket encryption, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.ENCRYPTION: ""})
        logger.debug(f"Get bucket encryption done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_bucket_encryption, GetServerSideEncryptionResult)

    async def delete_bucket_encryption(self):
        """删除Bucket加密配置。如果Bucket加密没有设置，也返回成功。"""
        logger.debug(f"Start to delete bucket encryption, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("DELETE", params={AsyncBucket.ENCRYPTION: ""})
        logger.debug(f"Delete bucket encryption done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def put_bucket_tagging(self, tagging, headers=None):
        """

        :param str key: 上传tagging的对象名称，不能为空。

        :param tagging: tag 标签内容
        :type tagging: :class:`Tagging <oss2.models.Tagging>` 对象

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to put object tagging, bucket: {self.bucket_name} tagging: {tagging}")

        headers = http.Headers(headers)

        data = self.__convert_data(Tagging, xml_utils.to_put_tagging, tagging)
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.TAGGING: ""}, headers=headers)

        logger.debug(f"Put bucket tagging done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_bucket_tagging(self):
        """
        :param str key: 要获取tagging的对象名称
        :param dict params: 请求参数
        :return: :class:`GetTaggingResult<oss2.models.GetTaggingResult>`
        """
        logger.debug(f"Start to get bucket tagging, bucket: {self.bucket_name}")

        resp = await self.__do_bucket("GET", params={AsyncBucket.TAGGING: ""})

        logger.debug(f"Get bucket tagging done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_tagging, GetTaggingResult)

    async def delete_bucket_tagging(self, params=None):
        """
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to delete bucket tagging, bucket: {self.bucket_name}")

        if params is None:
            params = dict()

        if AsyncBucket.TAGGING not in params:
            params[AsyncBucket.TAGGING] = ""

        resp = await self.__do_bucket("DELETE", params=params)

        logger.debug(f"Delete bucket tagging done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def list_object_versions(
        self, prefix="", delimiter="", key_marker="", max_keys=100, versionid_marker="", headers=None
    ):
        """根据前缀罗列Bucket里的文件的版本。

        :param str prefix: 只罗列文件名为该前缀的文件
        :param str delimiter: 分隔符。可以用来模拟目录
        :param str key_marker: 分页标志。首次调用传空串，后续使用返回值的next_marker
        :param int max_keys: 最多返回文件的个数，文件和目录的和不能超过该值
        :param str versionid_marker: 设定结果从key-marker对象的
            versionid-marker之后按新旧版本排序开始返回，该版本不会在返回的结果当中。

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :return: :class:`ListObjectVersionsResult <oss2.models.ListObjectVersionsResult>`
        """
        logger.debug(
            f"Start to List object versions, bucket: {self.bucket_name}, prefix: {prefix}, delimiter: {delimiter},"
            f"key_marker: {key_marker}, versionid_marker: {versionid_marker}, max-keys: {max_keys}"
        )

        headers = http.Headers(headers)

        resp = await self.__do_bucket(
            "GET",
            params={
                "prefix": prefix,
                "delimiter": delimiter,
                "key-marker": key_marker,
                "version-id-marker": versionid_marker,
                "max-keys": str(max_keys),
                "encoding-type": "url",
                AsyncBucket.VERSIONS: "",
            },
            headers=headers,
        )
        logger.debug(f"List object versions done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_list_object_versions, ListObjectVersionsResult)

    async def put_bucket_versioning(self, config, headers=None):
        """

        :param str operation: 设置bucket是否开启多版本特性，可取值为:[Enabled,Suspend]

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to put object versioning, bucket: {self.bucket_name}")
        data = self.__convert_data(BucketVersioningConfig, xml_utils.to_put_bucket_versioning, config)

        headers = http.Headers(headers)
        headers["Content-MD5"] = utils.content_md5(data)

        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.VERSIONING: ""}, headers=headers)
        logger.debug(f"Put bucket versiong done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_bucket_versioning(self):
        """
        :return: :class:`GetBucketVersioningResult<oss2.models.GetBucketVersioningResult>`
        """
        logger.debug(f"Start to get bucket versioning, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.VERSIONING: ""})
        logger.debug(f"Get bucket versiong done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_get_bucket_versioning, GetBucketVersioningResult)

    async def put_bucket_policy(self, policy):
        """设置bucket授权策略, 具体policy书写规则请参考官方文档

        :param str policy: 授权策略
        """
        logger.debug(f"Start to put bucket policy, bucket: {self.bucket_name}, policy: {policy}")
        resp = await self.__do_bucket(
            "PUT", data=policy, params={AsyncBucket.POLICY: ""}, headers={"Content-MD5": utils.content_md5(policy)}
        )
        logger.debug(f"Put bucket policy done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_bucket_policy(self):
        """获取bucket授权策略

        :return: :class:`GetBucketPolicyResult <oss2.models.GetBucketPolicyResult>`
        """

        logger.debug(f"Start to get bucket policy, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.POLICY: ""})
        logger.debug(f"Get bucket policy done, req_id: {resp.request_id}, status_code: {resp.status}")
        return GetBucketPolicyResult(resp)

    async def delete_bucket_policy(self):
        """删除bucket授权策略
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to delete bucket policy, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("DELETE", params={AsyncBucket.POLICY: ""})
        logger.debug(f"Delete bucket policy done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def put_bucket_request_payment(self, payer):
        """设置付费者。

        :param input: :class: str
        """
        data = xml_utils.to_put_bucket_request_payment(payer)
        logger.debug(f"Start to put bucket request payment, bucket: {self.bucket_name}, payer: {payer}")
        resp = await self.__do_bucket(
            "PUT", data=data, params={AsyncBucket.REQUESTPAYMENT: ""}, headers={"Content-MD5": utils.content_md5(data)}
        )
        logger.debug(f"Put bucket request payment done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_bucket_request_payment(self):
        """获取付费者设置。

        :return: :class:`GetBucketRequestPaymentResult <oss2.models.GetBucketRequestPaymentResult>`
        """
        logger.debug(f"Start to get bucket request payment, bucket: {self.bucket_name}.")
        resp = await self.__do_bucket("GET", params={AsyncBucket.REQUESTPAYMENT: ""})
        logger.debug(f"Get bucket request payment done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_get_bucket_request_payment, GetBucketRequestPaymentResult)

    async def put_bucket_qos_info(self, bucket_qos_info):
        """配置bucket的QoSInfo

        :param bucket_qos_info :class:`BucketQosInfo <oss2.models.BucketQosInfo>`
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to put bucket qos info, bucket: {self.bucket_name}")
        data = self.__convert_data(BucketQosInfo, xml_utils.to_put_qos_info, bucket_qos_info)

        headers = http.Headers()
        headers["Content-MD5"] = utils.content_md5(data)
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.QOS_INFO: ""}, headers=headers)
        logger.debug(f"Get bucket qos info done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_bucket_qos_info(self):
        """获取bucket的QoSInfo

        :return: :class:`GetBucketQosInfoResult <oss2.models.GetBucketQosInfoResult>`
        """
        logger.debug(f"Start to get bucket qos info, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.QOS_INFO: ""})
        logger.debug(f"Get bucket qos info, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_get_qos_info, GetBucketQosInfoResult)

    async def delete_bucket_qos_info(self):
        """删除bucket的QoSInfo

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to delete bucket qos info, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("DELETE", params={AsyncBucket.QOS_INFO: ""})
        logger.debug(f"Delete bucket qos info done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def set_bucket_storage_capacity(self, user_qos):
        """设置Bucket的容量，单位GB

        :param user_qos :class:`BucketUserQos <oss2.models.BucketUserQos>`
        """
        logger.debug(f"Start to set bucket storage capacity: {self.bucket_name}")
        data = xml_utils.to_put_bucket_user_qos(user_qos)
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.USER_QOS: ""})
        logger.debug(f"Set bucket storage capacity done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_bucket_storage_capacity(self):
        """获取bucket的容量信息。

        :return: :class:`GetBucketUserQosResult <oss2.models.GetBucketUserQosResult>`
        """
        logger.debug(f"Start to get bucket storage capacity, bucket:{self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.USER_QOS: ""})
        logger.debug(f"Get bucket storage capacity done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_get_bucket_user_qos, GetBucketUserQosResult)

    async def put_async_fetch_task(self, task_config):
        """创建一个异步获取文件到bucket的任务。

        :param task_config: 任务配置
        :type task_config: class:`AsyncFetchTaskConfiguration <oss2.models.AsyncFetchTaskConfiguration>`

        :return: :class:`PutAsyncFetchTaskResult <oss2.models.PutAsyncFetchTaskResult>`
        """
        logger.debug(f"Start to put async fetch task, bucket:{self.bucket_name}")
        data = xml_utils.to_put_async_fetch_task(task_config)
        headers = http.Headers()
        headers["Content-MD5"] = utils.content_md5(data)
        resp = await self.__do_bucket("POST", data=data, params={AsyncBucket.ASYNC_FETCH: ""}, headers=headers)
        logger.debug(f"Put async fetch task done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_put_async_fetch_task_result, PutAsyncFetchTaskResult)

    async def get_async_fetch_task(self, task_id):
        """获取一个异步获取文件到bucket的任务信息。

        :param str task_id: 任务id
        :return: :class:`GetAsyncFetchTaskResult <oss2.models.GetAsyncFetchTaskResult>`
        """
        logger.debug(f"Start to get async fetch task, bucket:{self.bucket_name}, task_id:{task_id}")
        resp = await self.__do_bucket("GET", headers={OSS_TASK_ID: task_id}, params={AsyncBucket.ASYNC_FETCH: ""})
        logger.debug(f"Put async fetch task done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_get_async_fetch_task_result, GetAsyncFetchTaskResult)

    async def put_bucket_inventory_configuration(self, inventory_configuration):
        """设置bucket清单配置

        :param inventory_configuration :class:`InventoryConfiguration <oss2.models.InventoryConfiguration>`
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to put bucket inventory configuration, bucket: {self.bucket_name}")
        data = self.__convert_data(
            InventoryConfiguration, xml_utils.to_put_inventory_configuration, inventory_configuration
        )

        headers = http.Headers()
        headers["Content-MD5"] = utils.content_md5(data)
        resp = await self.__do_bucket(
            "PUT",
            data=data,
            params={AsyncBucket.INVENTORY: "", AsyncBucket.INVENTORY_CONFIG_ID: inventory_configuration.inventory_id},
            headers=headers,
        )
        logger.debug(f"Put bucket inventory configuration done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_bucket_inventory_configuration(self, inventory_id):
        """获取指定的清单配置。

        :param str inventory_id : 清单配置id
        :return: :class:`GetInventoryConfigurationResult <oss2.models.GetInventoryConfigurationResult>`
        """
        logger.debug(f"Start to get bucket inventory configuration, bucket: {self.bucket_name}")
        resp = await self.__do_bucket(
            "GET", params={AsyncBucket.INVENTORY: "", AsyncBucket.INVENTORY_CONFIG_ID: inventory_id}
        )
        logger.debug(f"Get bucket inventory cinfguration done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(
            resp, xml_utils.parse_get_bucket_inventory_configuration, GetInventoryConfigurationResult
        )

    async def list_bucket_inventory_configurations(self, continuation_token=None):
        """罗列清单配置，默认单次最大返回100条配置，如果存在超过100条配置，罗列结果将会分页，
        分页信息保存在 class:`ListInventoryConfigurationResult <oss2.models.ListInventoryConfigurationResult>`中。

        :param str continuation_token: 分页标识, 默认值为None, 如果上次罗列不完整，这里设置为上次罗列结果中的next_continuation_token值。
        :return: :class:`ListInventoryConfigurationResult <oss2.models.ListInventoryConfigurationResult>`
        """
        logger.debug(f"Start to list bucket inventory configuration, bucket: {self.bucket_name}")
        params = {AsyncBucket.INVENTORY: ""}
        if continuation_token is not None:
            params[AsyncBucket.CONTINUATION_TOKEN] = continuation_token
        resp = await self.__do_bucket("GET", params=params)
        logger.debug(
            f"List bucket inventory configuration done, req_id: {resp.request_id}, status_code: {resp.status}"
        )

        return self._parse_result(
            resp, xml_utils.parse_list_bucket_inventory_configurations, ListInventoryConfigurationsResult
        )

    async def delete_bucket_inventory_configuration(self, inventory_id):
        """删除指定的清单配置

        :param str inventory_id : 清单配置id
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(
            f"Start to delete bucket inventory configuration, bucket: {self.bucket_name}, configuration id: {inventory_id}."
        )
        resp = await self.__do_bucket(
            "DELETE", params={AsyncBucket.INVENTORY: "", AsyncBucket.INVENTORY_CONFIG_ID: inventory_id}
        )
        logger.debug(f"Delete bucket inventory configuration, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def init_bucket_worm(self, retention_period_days=None):
        """创建一条合规保留策略

        :param int retention_period_days : 指定object的保留天数
        :return: :class:`InitBucketWormResult <oss2.models.InitBucketWormResult>`
        """
        logger.debug(
            f"Start to init bucket worm, bucket: {self.bucket_name}, retention_period_days: {retention_period_days}."
        )
        data = xml_utils.to_put_init_bucket_worm(retention_period_days)
        headers = http.Headers()
        headers["Content-MD5"] = utils.content_md5(data)
        resp = await self.__do_bucket("POST", data=data, params={AsyncBucket.WORM: ""}, headers=headers)
        logger.debug(f"init bucket worm done, req_id: {resp.request_id}, status_code: {resp.status}")

        result = InitBucketWormResult(resp)
        result.worm_id = resp.headers.get("x-oss-worm-id")
        return result

    async def abort_bucket_worm(self):
        """删除一条合规保留策略
        只有未锁定保留策略的状态下才能删除，一旦锁定bucket数据将处于保护状态。

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to abort bucket worm, bucket: {self.bucket_name}.")
        resp = await self.__do_bucket("DELETE", params={AsyncBucket.WORM: ""})
        logger.debug(f"abort bucket worm done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def complete_bucket_worm(self, worm_id=None):
        """锁定一条合规保留策略

        :param str worm_id : 合规保留策略的id。
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to complete bucket worm, bucket: {self.bucket_name}, worm_id: {worm_id}.")
        resp = await self.__do_bucket("POST", params={AsyncBucket.WORM_ID: worm_id})
        logger.debug(f"complete bucket worm done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def extend_bucket_worm(self, worm_id=None, retention_period_days=None):
        """延长已经锁定的合规保留策略的object保护天数。

        :param str worm_id : 合规保留策略的id。
        :param int retention_period_days : 指定object的保留天数
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        data = xml_utils.to_put_extend_bucket_worm(retention_period_days)
        headers = http.Headers()
        headers["Content-MD5"] = utils.content_md5(data)
        logger.debug(
            f"Start to extend bucket worm, bucket: {self.bucket_name}, worm_id: {worm_id}, retention_period_days: {retention_period_days}."
        )
        resp = await self.__do_bucket(
            "POST", data=data, params={AsyncBucket.WORM_ID: worm_id, AsyncBucket.WORM_EXTEND: ""}, headers=headers
        )
        logger.debug(f"extend bucket worm done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_bucket_worm(self):
        """获取合规保留策略

        :return: :class:`GetBucketWormResult <oss2.models.GetBucketWormResult>`
        """
        logger.debug(f"Start to get bucket worm, bucket: {self.bucket_name}.")
        resp = await self.__do_bucket("GET", params={AsyncBucket.WORM: ""})
        logger.debug(f"get bucket worm done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_get_bucket_worm_result, GetBucketWormResult)

    async def put_bucket_replication(self, rule):
        """设置bucket跨区域复制规则

        :param rule :class:`ReplicationRule <oss2.models.ReplicationRule>`
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to put bucket replication: {self.bucket_name}")
        data = xml_utils.to_put_bucket_replication(rule)
        headers = http.Headers()
        headers["Content-MD5"] = utils.content_md5(data)
        resp = await self.__do_bucket(
            "POST", data=data, params={AsyncBucket.REPLICATION: "", "comp": "add"}, headers=headers
        )
        logger.debug(f"Put bucket replication done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_bucket_replication(self):
        """获取bucket跨区域复制规则

        :return: :class:`GetBucketReplicationResult <oss2.models.GetBucketReplicationResult>`
        """
        logger.debug(f"Start to get bucket replication: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.REPLICATION: ""})
        logger.debug(f"Get bucket replication done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_get_bucket_replication_result, GetBucketReplicationResult)

    async def delete_bucket_replication(self, rule_id):
        """停止Bucket的跨区域复制并删除Bucket的复制配置
        :param str rule_id: Bucket跨区域复制规则的id。

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to delete bucket replication: {self.bucket_name}")
        data = xml_utils.to_delete_bucket_replication(rule_id)
        headers = http.Headers()
        headers["Content-MD5"] = utils.content_md5(data)
        resp = await self.__do_bucket(
            "POST", data=data, params={AsyncBucket.REPLICATION: "", "comp": "delete"}, headers=headers
        )
        logger.debug(f"Delete bucket replication done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_bucket_replication_location(self):
        """获取可复制到的Bucket所在的地域

        :return: :class:`ReplicationLocation <oss2.models.GetBucketReplicationLocationResult>`
        """
        logger.debug(f"Start to get bucket replication location: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.REPLICATION_LOCATION: ""})
        logger.debug(f"Get bucket replication location done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(
            resp, xml_utils.parse_get_bucket_replication_location_result, GetBucketReplicationLocationResult
        )

    async def get_bucket_replication_progress(self, rule_id):
        """获取获取某个Bucket的跨区域复制进度

        :param str rule_id: Bucket跨区域复制规则的id。
        :return: :class:`GetBucketReplicationProgressResult <oss2.models.GetBucketReplicationProgressResult>`
        """
        logger.debug(f"Start to get bucket replication progress: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.REPLICATION_PROGRESS: "", "rule-id": rule_id})
        logger.debug(f"Get bucket replication progress done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(
            resp, xml_utils.parse_get_bucket_replication_progress_result, GetBucketReplicationProgressResult
        )

    async def _get_bucket_config(self, config):
        """获得Bucket某项配置，具体哪种配置由 `config` 指定。该接口直接返回 `RequestResult` 对象。
        通过read()接口可以获得XML字符串。不建议使用。

        :param str config: 可以是 `Bucket.ACL` 、 `Bucket.LOGGING` 等。

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to get bucket config, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={config: ""})
        logger.debug(f"Get bucket config done, req_id: {resp.request_id}, status_code: {resp.status}")
        return resp

    async def put_bucket_transfer_acceleration(self, enabled):
        """为存储空间（Bucket）配置传输加速

        :param str enabled : 是否开启传输加速。true：开启传输加速; false：关闭传输加速.
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to bucket transfer acceleration, bucket: {self.bucket_name}, enabled: {enabled}.")
        data = xml_utils.to_put_bucket_transfer_acceleration(enabled)
        headers = http.Headers()
        headers["Content-MD5"] = utils.content_md5(data)
        resp = await self.__do_bucket(
            "PUT", data=data, params={AsyncBucket.TRANSFER_ACCELERATION: ""}, headers=headers
        )
        logger.debug(f"bucket transfer acceleration done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_bucket_transfer_acceleration(self):
        """获取目标存储空间（Bucket）的传输加速配置

        :return: :class:`GetBucketTransferAccelerationResult <oss2.models.GetBucketTransferAccelerationResult>`
        """
        logger.debug(f"Start to get bucket transfer acceleration: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.TRANSFER_ACCELERATION: ""})
        logger.debug(f"Get bucket transfer acceleration done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(
            resp, xml_utils.parse_get_bucket_transfer_acceleration_result, GetBucketTransferAccelerationResult
        )

    async def create_bucket_cname_token(self, domain):
        """创建域名所有权验证所需的CnameToken。

        :param str domain : 绑定的Cname名称。
        :return: :class:`CreateBucketCnameTokenResult <oss2.models.CreateBucketCnameTokenResult>`
        """
        logger.debug(f"Start to create bucket cname token, bucket: {self.bucket_name}.")
        data = xml_utils.to_bucket_cname_configuration(domain)
        resp = await self.__do_bucket("POST", data=data, params={AsyncBucket.CNAME: "", AsyncBucket.COMP: "token"})
        logger.debug(f"bucket cname token done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_create_bucket_cname_token, CreateBucketCnameTokenResult)

    async def get_bucket_cname_token(self, domain):
        """获取已创建的CnameToken。

        :param str domain : 绑定的Cname名称。
        :return: :class:`GetBucketCnameTokenResult <oss2.models.GetBucketCnameTokenResult>`
        """
        logger.debug(f"Start to get bucket cname: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.CNAME: domain, AsyncBucket.COMP: "token"})
        logger.debug(f"Get bucket cname done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_bucket_cname_token, GetBucketCnameTokenResult)

    async def put_bucket_cname(self, input):
        """为某个存储空间（Bucket）绑定自定义域名。

        :param input: PutBucketCnameRequest类型，包含了证书和自定义域名信息
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to add bucket cname, bucket: {self.bucket_name}.")
        data = xml_utils.to_bucket_cname_configuration(input.domain, input.cert)
        resp = await self.__do_bucket("POST", data=data, params={AsyncBucket.CNAME: "", AsyncBucket.COMP: "add"})
        logger.debug(f"bucket cname done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def list_bucket_cname(self):
        """查询某个存储空间（Bucket）下绑定的所有Cname列表。

        :return: :class:`ListBucketCnameResult <oss2.models.ListBucketCnameResult>`
        """
        logger.debug(f"Start to do query list bucket cname: {self.bucket_name}")

        resp = await self.__do_bucket("GET", params={AsyncBucket.CNAME: ""})
        logger.debug(f"query list bucket cname done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_list_bucket_cname, ListBucketCnameResult)

    async def delete_bucket_cname(self, domain):
        """删除某个存储空间（Bucket）已绑定的Cname

        :param str domain : 绑定的Cname名称。
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to delete bucket cname: {self.bucket_name}")
        data = xml_utils.to_bucket_cname_configuration(domain)
        resp = await self.__do_bucket("POST", data=data, params={AsyncBucket.CNAME: "", AsyncBucket.COMP: "delete"})
        logger.debug(f"delete bucket cname done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def open_bucket_meta_query(self):
        """为存储空间（Bucket）开启元数据管理功能

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to bucket meta query, bucket: {self.bucket_name}.")
        resp = await self.__do_bucket("POST", params={AsyncBucket.META_QUERY: "", "comp": "add"})
        logger.debug(f"bucket meta query done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_bucket_meta_query_status(self):
        """获取指定存储空间（Bucket）的元数据索引库信息。

        :return: :class:`GetBucketMetaQueryResult <oss2.models.GetBucketMetaQueryResult>`
        """
        logger.debug(f"Start to get bucket meta query: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.META_QUERY: ""})
        logger.debug(f"Get bucket meta query done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_bucket_meta_query_result, GetBucketMetaQueryResult)

    async def do_bucket_meta_query(self, do_meta_query_request):
        """查询满足指定条件的文件（Object），并按照指定字段和排序方式列出文件信息。

        :param do_meta_query_request :class:`MetaQuery <oss2.models.MetaQuery>`
        :return: :class:`DoBucketMetaQueryResult <oss2.models.DoBucketMetaQueryResult>`
        """
        logger.debug(f"Start to do bucket meta query: {self.bucket_name}")

        data = self.__convert_data(MetaQuery, xml_utils.to_do_bucket_meta_query_request, do_meta_query_request)
        resp = await self.__do_bucket(
            "POST", data=data, params={AsyncBucket.META_QUERY: "", AsyncBucket.COMP: "query"}
        )
        logger.debug(f"do bucket meta query done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_do_bucket_meta_query_result, DoBucketMetaQueryResult)

    async def close_bucket_meta_query(self):
        """关闭存储空间（Bucket）的元数据管理功能

        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to close bucket meta query: {self.bucket_name}")
        resp = await self.__do_bucket("POST", params={AsyncBucket.META_QUERY: "", AsyncBucket.COMP: "delete"})
        logger.debug(f"bucket meta query done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def put_bucket_access_monitor(self, status):
        """更新 Bucket 访问跟踪状态。

        :param str status : bucket访问跟踪的开启状态
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to put bucket access monitor, bucket: {self.bucket_name}.")
        data = xml_utils.to_put_bucket_access_monitor(status)
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.ACCESS_MONITOR: ""})
        logger.debug(f"bucket access monitor done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_bucket_access_monitor(self):
        """获取当前Bucket的访问跟踪的状态。

        :return: :class:`GetBucketAccessMonitorResult <oss2.models.GetBucketAccessMonitorResult>`
        """
        logger.debug(f"Start to get bucket access monitor: {self.bucket_name}")

        resp = await self.__do_bucket("GET", params={AsyncBucket.ACCESS_MONITOR: ""})
        logger.debug(f"query list bucket cname done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_bucket_access_monitor_result, GetBucketAccessMonitorResult)

    async def get_bucket_resource_group(self):
        """查询存储空间（Bucket）的资源组ID。

        :return: :class:`GetBucketResourceGroupResult <oss2.models.GetBucketResourceGroupResult>`
        """
        logger.debug(f"Start to get bucket resource group: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.RESOURCE_GROUP: ""})
        logger.debug(f"Get bucket resource group done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_get_bucket_resource_group_result, GetBucketResourceGroupResult)

    async def put_bucket_resource_group(self, resourceGroupId):
        """为存储空间（Bucket）配置所属资源组。

        :param str resourceGroupId : Bucket所属的资源组ID。
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to put bucket resource group, bucket: {self.bucket_name}.")
        data = xml_utils.to_put_bucket_resource_group(resourceGroupId)
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.RESOURCE_GROUP: ""})
        logger.debug(f"bucket resource group done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def put_bucket_style(self, styleName, content):
        """新增图片样式。

        :param str styleName : 样式名称。
        :param str content : 图片样式内容，图片样式可以包含一个或多个图片处理操作。
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to put bucket style, bucket: {self.bucket_name}.")

        data = xml_utils.to_put_bucket_style(content)
        resp = await self.__do_bucket(
            "PUT", data=data, params={AsyncBucket.STYLE: "", AsyncBucket.STYLE_NAME: styleName}
        )
        logger.debug(f"bucket style done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_bucket_style(self, styleName):
        """查询某个Bucket下指定的图片样式信息。

        :param str styleName : 样式名称。
        :return: :class:`GetBucketStyleResult <oss2.models.GetBucketStyleResult>`
        """
        logger.debug(f"Start to get bucket style: {self.bucket_name}")

        resp = await self.__do_bucket("GET", params={AsyncBucket.STYLE: "", AsyncBucket.STYLE_NAME: styleName})
        logger.debug(f"Get bucket style done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_get_bucket_style_result, GetBucketStyleResult)

    async def list_bucket_style(self):
        """查询某个Bucket下已创建的所有图片样式。

        :return: :class:`ListBucketStyleResult <oss2.models.ListBucketStyleResult>`
        """
        logger.debug(f"Start to list bucket style: {self.bucket_name}")

        resp = await self.__do_bucket("GET", params={AsyncBucket.STYLE: ""})
        logger.debug(f"query list bucket style done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_list_bucket_style, ListBucketStyleResult)

    async def delete_bucket_style(self, styleName):
        """删除某个Bucket下指定的图片样式。

        :param str styleName : 样式名称。
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to delete bucket style: {self.bucket_name}")

        resp = await self.__do_bucket("DELETE", params={AsyncBucket.STYLE: "", AsyncBucket.STYLE_NAME: styleName})
        logger.debug(f"delete bucket style done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def async_process_object(self, key, process, headers=None):
        """异步处理多媒体接口。

        :param str key: 处理的多媒体的对象名称
        :param str process: 处理的字符串，例如"video/convert,f_mp4,vcodec_h265,s_1920x1080,vb_2000000,fps_30,acodec_aac,ab_100000,sn_1|sys/saveas,o_dGVzdC5qcGc,b_dGVzdA"

        :param headers: HTTP头部
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict
        """

        headers = http.Headers(headers)

        logger.debug(f"Start to async process object, bucket: {self.bucket_name}, key: {key}, process: {process}")
        process_data = "%s=%s" % (AsyncBucket.ASYNC_PROCESS, process)
        resp = await self.__do_object(
            "POST", key, params={AsyncBucket.ASYNC_PROCESS: ""}, headers=headers, data=process_data
        )
        logger.debug(f"Async process object done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_async_process_object, AsyncProcessObject)

    async def put_bucket_callback_policy(self, callbackPolicy):
        """设置bucket回调策略

        :param str callbackPolicy: 回调策略
        """
        logger.debug(
            f"Start to put bucket callback policy, bucket: {self.bucket_name}, callback policy: {callbackPolicy}"
        )
        data = xml_utils.to_do_bucket_callback_policy_request(callbackPolicy)
        resp = await self.__do_bucket(
            "PUT", data=data, params={AsyncBucket.POLICY: "", AsyncBucket.COMP: AsyncBucket.CALLBACK}
        )
        logger.debug(f"Put bucket callback policy done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_bucket_callback_policy(self):
        """获取bucket回调策略
        :return: :class:`GetBucketPolicyResult <oss2.models.CallbackPolicyResult>`
        """

        logger.debug(f"Start to get bucket callback policy, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.POLICY: "", AsyncBucket.COMP: AsyncBucket.CALLBACK})
        logger.debug(f"Get bucket callback policy done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_callback_policy_result, CallbackPolicyResult)

    async def delete_bucket_callback_policy(self):
        """删除bucket回调策略
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to delete bucket callback policy, bucket: {self.bucket_name}")
        resp = await self.__do_bucket(
            "DELETE", params={AsyncBucket.POLICY: "", AsyncBucket.COMP: AsyncBucket.CALLBACK}
        )
        logger.debug(f"Delete bucket callback policy done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def put_bucket_archive_direct_read(self, enabled=False):
        """设置归档直读

        :param boolean enabled: Bucket是否开启归档直读
        """
        logger.debug(f"Start to put bucket archive direct read, bucket: {self.bucket_name}, enabled: {enabled}")
        data = xml_utils.to_put_bucket_archive_direct_read(enabled)
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.ARCHIVE_DIRECT_READ: ""})
        logger.debug(f"bucket archive direct read done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_bucket_archive_direct_read(self):
        """获取归档直读
        :return: :class:`GetBucketArchiveDirectReadResult <oss2.models.GetBucketArchiveDirectReadResult>`
        """

        logger.debug(f"Start to get bucket archive direct read, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.ARCHIVE_DIRECT_READ: ""})
        logger.debug(f"Get bucket archive direct read done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(
            resp, xml_utils.parse_get_bucket_archive_direct_read, GetBucketArchiveDirectReadResult
        )

    async def put_bucket_https_config(self, httpsConfig):
        """Bucket开启或关闭TLS版本设置。
        :param httpsConfig: TLS版本信息设置
        """
        logger.debug(f"Start to put bucket https config, bucket: {self.bucket_name}, https config: {httpsConfig}")
        data = xml_utils.to_do_bucket_https_config_request(httpsConfig)
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.HTTPS_CONFIG: ""})
        logger.debug(f"Put bucket https config done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def create_bucket_data_redundancy_transition(self, targetType):
        """为Bucket创建存储冗余转换任务。

        :param str targetType: 目标存储冗余类型
        """
        logger.debug(
            f"Start to create bucket data redundancy transition, bucket: {self.bucket_name}, target type: {targetType}"
        )

        resp = await self.__do_bucket(
            "POST", params={AsyncBucket.REDUNDANCY_TRANSITION: "", AsyncBucket.TARGET_REDUNDANCY_TYPE: targetType}
        )
        logger.debug(
            f"Create bucket data redundancy transition done, req_id: {resp.request_id}, status_code: {resp.status}"
        )

        return self._parse_result(
            resp, xml_utils.parse_create_data_redundancy_transition_result, CreateDataRedundancyTransitionResult
        )

    async def get_bucket_data_redundancy_transition(self, taskId):
        """获取存储冗余转换任务。
        :return: :class:`DataRedundancyTransitionInfoResult <oss2.models.DataRedundancyTransitionInfoResult>`
        """

        logger.debug(f"Start to get bucket data redundancy transition, bucket: {self.bucket_name}")
        resp = await self.__do_bucket(
            "GET", params={AsyncBucket.REDUNDANCY_TRANSITION: "", AsyncBucket.REDUNDANCY_TRANSITION_TASK_ID: taskId}
        )
        logger.debug(
            f"Get bucket data redundancy transition done, req_id: {resp.request_id}, status_code: {resp.status}"
        )
        return self._parse_result(
            resp, xml_utils.parse_get_bucket_data_redundancy_transition, DataRedundancyTransitionInfoResult
        )

    async def delete_bucket_data_redundancy_transition(self, taskId):
        """删除存储冗余转换任务。
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to delete bucket data redundancy transition, bucket: {self.bucket_name}")
        resp = await self.__do_bucket(
            "DELETE", params={AsyncBucket.REDUNDANCY_TRANSITION: "", AsyncBucket.REDUNDANCY_TRANSITION_TASK_ID: taskId}
        )
        logger.debug(
            f"Delete bucket data redundancy transition done, req_id: {resp.request_id}, status_code: {resp.status}"
        )
        return RequestResult(resp)

    async def get_bucket_https_config(self):
        """查看Bucket的TLS版本设置。
        :return: :class:`HttpsConfigResult <oss2.models.HttpsConfigResult>`
        """
        logger.debug(f"Start to get bucket https config, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.HTTPS_CONFIG: ""})
        logger.debug(f"Get bucket https config done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_bucket_https_config, HttpsConfigResult)

    async def list_bucket_data_redundancy_transition(self):
        """列举某个Bucket下所有的存储冗余转换任务。

        :return: :class:`ListBucketDataRedundancyTransitionResult <oss2.models.ListBucketDataRedundancyTransitionResult>`
        """
        logger.debug(f"Start to do query list bucket data redundancy transition: {self.bucket_name}")

        resp = await self.__do_bucket("GET", params={AsyncBucket.REDUNDANCY_TRANSITION: ""})
        logger.debug(
            f"query list bucket data redundancy transition done, req_id: {resp.request_id}, status_code: {resp.status}"
        )
        return self._parse_result(
            resp, xml_utils.parse_list_bucket_data_redundancy_transition, ListBucketDataRedundancyTransitionResult
        )

    async def create_access_point(self, accessPoint):
        """创建接入点
        :param accessPoint :class:`CreateAccessPointRequest <oss2.models.CreateAccessPointRequest>`
        :return: :class:`CreateAccessPointResult <oss2.models.CreateAccessPointResult>`
        """
        logger.debug(f"Start to create access point, bucket: {self.bucket_name}")
        data = xml_utils.to_do_create_access_point_request(accessPoint)
        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.ACCESS_POINT: ""})
        logger.debug(f"Create access point done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_create_access_point_result, CreateAccessPointResult)

    async def get_access_point(self, accessPointName):
        """获取接入点信息
        :param str accessPointName: 接入点名称
        :return: :class:`GetAccessPointResult <oss2.models.GetAccessPointResult>`
        """

        logger.debug(f"Start to get access point, bucket: {self.bucket_name}")
        headers = http.Headers()
        headers["x-oss-access-point-name"] = accessPointName
        resp = await self.__do_bucket("GET", params={AsyncBucket.ACCESS_POINT: ""}, headers=headers)
        logger.debug(f"Get access point done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_get_access_point_result, GetAccessPointResult)

    async def delete_access_point(self, accessPointName):
        """删除接入点
         :param str accessPointName: 接入点名称
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to delete access point, bucket: {self.bucket_name}")
        headers = http.Headers()
        headers["x-oss-access-point-name"] = accessPointName
        resp = await self.__do_bucket("DELETE", params={AsyncBucket.ACCESS_POINT: ""}, headers=headers)
        logger.debug(f"Delete access point done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def list_bucket_access_points(self, max_keys=100, continuation_token=""):
        """查询某个Bucket下所有接入点。
        param: int max_keys: 本次list返回access point的最大个数
        param: str continuation_token: list时指定的起始标记
        :return: :class:`ListAccessPointResult <oss2.models.ListAccessPointResult>`
        """
        logger.debug(f"Start to list bucket access point: {self.bucket_name}")

        resp = await self.__do_bucket(
            "GET",
            params={AsyncBucket.ACCESS_POINT: "", "max-keys": str(max_keys), "continuation-token": continuation_token},
        )
        logger.debug(f"query list bucket access point done, req_id: {resp.request_id}, status_code: {resp.status}")
        return self._parse_result(resp, xml_utils.parse_list_access_point_result, ListAccessPointResult)

    async def put_access_point_policy(self, accessPointName, accessPointPolicy):
        """设置接入点策略
        :param str accessPointName: 接入点名称
        :param str accessPointPolicy : 接入点策略
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(
            f"Start to put access point policy, bucket: {self.bucket_name}, accessPointPolicy: {accessPointPolicy}"
        )
        headers = http.Headers()
        headers["x-oss-access-point-name"] = accessPointName
        resp = await self.__do_bucket(
            "PUT", data=accessPointPolicy, params={AsyncBucket.ACCESS_POINT_POLICY: ""}, headers=headers
        )
        logger.debug(f"Create access point policy done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def get_access_point_policy(self, accessPointName):
        """获取接入点策略
        :param str accessPointName: 接入点名称
        :return: :class:`GetAccessPointPolicyResult <oss2.models.GetAccessPointPolicyResult>`
        """

        logger.debug(f"Start to get access point policy, bucket: {self.bucket_name}")
        headers = http.Headers()
        headers["x-oss-access-point-name"] = accessPointName
        resp = await self.__do_bucket("GET", params={AsyncBucket.ACCESS_POINT_POLICY: ""}, headers=headers)
        logger.debug(f"Get access point policy done, req_id: {resp.request_id}, status_code: {resp.status}")
        return GetAccessPointPolicyResult(resp)

    async def delete_access_point_policy(self, accessPointName):
        """删除接入点策略
        :param str accessPointName: 接入点名称
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to delete access point policy, bucket: {self.bucket_name}")
        headers = http.Headers()
        headers["x-oss-access-point-name"] = accessPointName
        resp = await self.__do_bucket("DELETE", params={AsyncBucket.ACCESS_POINT_POLICY: ""}, headers=headers)
        logger.debug(f"Delete access point policy done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def put_bucket_public_access_block(self, block_public_access=False):
        """为Bucket开启阻止公共访问。

        :param bool block_public_access : 是否开启阻止公共访问。
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(
            f"Start to bucket put public access block, bucket: {self.bucket_name}, enabled: {block_public_access}."
        )
        data = xml_utils.to_put_public_access_block_request(block_public_access)

        resp = await self.__do_bucket("PUT", data=data, params={AsyncBucket.PUBLIC_ACCESS_BLOCK: ""})
        logger.debug(f"bucket public access block done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_bucket_public_access_block(self):
        """获取指定Bucket的阻止公共访问配置信息。

        :return: :class:`GetBucketPublicAccessBlockResult <oss2.models.GetBucketPublicAccessBlockResult>`
        """
        logger.debug(f"Start to get bucket public access block: {self.bucket_name}")
        resp = await self.__do_bucket("GET", params={AsyncBucket.PUBLIC_ACCESS_BLOCK: ""})
        logger.debug(f"Get bucket public access block done, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(
            resp, xml_utils.parse_get_public_access_block_result, GetBucketPublicAccessBlockResult
        )

    async def delete_bucket_public_access_block(self):
        """删除指定Bucket的阻止公共访问配置信息。
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to delete bucket public access block, bucket: {self.bucket_name}")
        resp = await self.__do_bucket("DELETE", params={AsyncBucket.PUBLIC_ACCESS_BLOCK: ""})
        logger.debug(f"Delete bucket public access block done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def put_access_point_public_access_block(self, access_point_name, block_public_access=False):
        """为接入点开启阻止公共访问。

        :param bool block_public_access : 是否开启阻止公共访问。
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(
            f"Start to put access point public access block, bucket: {self.bucket_name}, access point name: {access_point_name}, block public access: {block_public_access}."
        )
        data = xml_utils.to_put_public_access_block_request(block_public_access)

        resp = await self.__do_bucket(
            "PUT",
            data=data,
            params={AsyncBucket.PUBLIC_ACCESS_BLOCK: "", AsyncBucket.OSS_ACCESS_POINT_NAME: access_point_name},
        )
        logger.debug(f"access point public access block done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_access_point_public_access_block(self, access_point_name):
        """获取指定接入点的阻止公共访问配置信息。

        :return: :class:`GetBucketPublicAccessBlockResult <oss2.models.GetBucketPublicAccessBlockResult>`
        """
        logger.debug(
            f"Start to get access point public access block: {self.bucket_name}, access point name: {access_point_name}."
        )
        resp = await self.__do_bucket(
            "GET", params={AsyncBucket.PUBLIC_ACCESS_BLOCK: "", AsyncBucket.OSS_ACCESS_POINT_NAME: access_point_name}
        )
        logger.debug(
            f"Get access point public access block done, req_id: {resp.request_id}, status_code: {resp.status}"
        )

        return self._parse_result(
            resp, xml_utils.parse_get_public_access_block_result, GetBucketPublicAccessBlockResult
        )

    async def delete_access_point_public_access_block(self, access_point_name):
        """删除指定接入点的阻止公共访问配置信息。
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(
            f"Start to delete access point public access block, bucket: {self.bucket_name}, access point name: {access_point_name}."
        )
        resp = await self.__do_bucket(
            "DELETE",
            params={AsyncBucket.PUBLIC_ACCESS_BLOCK: "", AsyncBucket.OSS_ACCESS_POINT_NAME: access_point_name},
        )
        logger.debug(
            f"Delete access point public access block done, req_id: {resp.request_id}, status_code: {resp.status}"
        )
        return RequestResult(resp)

    async def put_bucket_requester_qos_info(self, uid, qos_configuration):
        """修改请求者在Bucket上的流控配置。

        :param str uid: 请求者UID
        :param qos_configuration :class:`QoSConfiguration <oss2.models.QoSConfiguration>`
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(
            f"Start to put bucket requester qos info, bucket: {self.bucket_name}, uid: {uid}, qos_configuration: {qos_configuration}."
        )

        if not uid:
            raise ClientError("uid should not be empty")

        data = xml_utils.to_put_qos_info(qos_configuration)

        resp = await self.__do_bucket(
            "PUT", data=data, params={AsyncBucket.REQUESTER_QOS_INFO: "", AsyncBucket.QOS_REQUESTER: uid}
        )
        logger.debug(f"put bucket requester qos info done, req_id: {resp.request_id}, status_code: {resp.status}")

        return RequestResult(resp)

    async def get_bucket_requester_qos_info(self, uid):
        """获取请求者在Bucket上的流控配置。

        :return: :class:`RequesterQoSInfoResult <oss2.models.RequesterQoSInfoResult>`
        """
        logger.debug(f"Start to get bucket requester qos info: {self.bucket_name}, uid: {uid}.")
        if not uid:
            raise ClientError("uid should not be empty")

        resp = await self.__do_bucket(
            "GET", params={AsyncBucket.REQUESTER_QOS_INFO: "", AsyncBucket.QOS_REQUESTER: uid}
        )
        logger.debug(f"Get bucket requester qos info, req_id: {resp.request_id}, status_code: {resp.status}")

        return self._parse_result(resp, xml_utils.parse_get_requester_qos_info, RequesterQoSInfoResult)

    async def list_bucket_requester_qos_infos(self, continuation_token="", max_keys=100):
        """列举所有对该Bucket的请求者流控配置。

        :param str continuation_token: 分页标志,首次调用传空串
        :param int max_keys: 最多返回数目
        :return: :class:`ListBucketRequesterQoSInfosResult <oss2.models.ListBucketRequesterQoSInfosResult>`
        """
        logger.debug(f"Start to do query list bucket requester qos infos: {self.bucket_name}")

        resp = await self.__do_bucket(
            "GET",
            params={
                AsyncBucket.REQUESTER_QOS_INFO: "",
                "continuation-token": continuation_token,
                "max-keys": str(max_keys),
            },
        )
        logger.debug(
            f"query list bucket requester qos infos done, req_id: {resp.request_id}, status_code: {resp.status}"
        )
        return self._parse_result(
            resp, xml_utils.parse_list_bucket_requester_qos_infos, ListBucketRequesterQoSInfosResult
        )

    async def delete_bucket_requester_qos_info(self, uid):
        """删除在Bucket上的请求者流控配置。
        :return: :class:`RequestResult <oss2.models.RequestResult>`
        """
        logger.debug(f"Start to delete bucket requester qos info, bucket: {self.bucket_name}, uid: {uid}.")
        if not uid:
            raise ClientError("uid should not be empty")

        resp = await self.__do_bucket(
            "DELETE", params={AsyncBucket.REQUESTER_QOS_INFO: "", AsyncBucket.QOS_REQUESTER: uid}
        )
        logger.debug(f"Delete bucket requester qos info done, req_id: {resp.request_id}, status_code: {resp.status}")
        return RequestResult(resp)

    async def __do_object(self, method, key, **kwargs):
        if not self.bucket_name:
            raise ClientError("Bucket name should not be null or empty.")
        if not key:
            raise ClientError("key should not be null or empty.")
        return await self._do(method, self.bucket_name, key, **kwargs)

    async def __do_bucket(self, method, **kwargs):
        return await self._do(method, self.bucket_name, "", **kwargs)

    def __convert_data(self, klass, converter, data):
        if isinstance(data, klass):
            return converter(data)
        else:
            return data
