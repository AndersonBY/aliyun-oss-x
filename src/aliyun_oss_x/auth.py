import hmac
import time
import hashlib
import logging
from urllib.parse import quote
from datetime import datetime, timezone

from .compat import to_bytes
from .exceptions import ClientError
from .utils import b64encode_as_string
from .headers import OSS_SECURITY_TOKEN
from .credentials import StaticCredentialsProvider

AUTH_VERSION_4 = "v4"
DEFAULT_SIGNED_HEADERS = ["content-type", "content-md5"]

logger = logging.getLogger(__name__)


def make_auth(access_key_id, access_key_secret):
    return AuthV4(access_key_id.strip(), access_key_secret.strip())


class AuthBase:
    """用于保存用户AccessKeyId、AccessKeySecret，以及计算签名的对象。"""

    def __init__(self, credentials_provider):
        self.credentials_provider = credentials_provider

    def _sign_rtmp_url(self, url, bucket_name, channel_name, expires, params):
        credentials = self.credentials_provider.get_credentials()
        if credentials.get_security_token():
            params["security-token"] = credentials.get_security_token()

        expiration_time = int(time.time()) + expires

        canonicalized_resource = "/%s/%s" % (bucket_name, channel_name)
        canonicalized_params = []

        if params:
            items = params.items()
            for k, v in items:
                if k != "OSSAccessKeyId" and k != "Signature" and k != "Expires" and k != "SecurityToken":
                    canonicalized_params.append((k, v))

        canonicalized_params.sort(key=lambda e: e[0])
        canon_params_str = ""
        for k, v in canonicalized_params:
            canon_params_str += "%s:%s\n" % (k, v)

        p = params if params else {}
        string_to_sign = str(expiration_time) + "\n" + canon_params_str + canonicalized_resource
        logger.debug("Sign Rtmp url: string to be signed = {0}".format(string_to_sign))

        h = hmac.new(to_bytes(credentials.get_access_key_secret()), to_bytes(string_to_sign), hashlib.sha1)
        signature = b64encode_as_string(h.digest())

        p["OSSAccessKeyId"] = credentials.get_access_key_id()
        p["Expires"] = str(expiration_time)
        p["Signature"] = signature

        return url + "?" + "&".join(_param_to_quoted_query(k, v) for k, v in p.items())

    def auth_version(self) -> str:
        return ""


class AnonymousAuth:
    """用于匿名访问。

    .. note::
        匿名用户只能读取public-read的Bucket，或只能读取、写入public-read-write的Bucket。
        不能进行Service、Bucket相关的操作，也不能罗列文件等。
    """

    def _sign_request(self, req, bucket_name, key):
        pass

    def _sign_url(self, req, bucket_name, key, expires, in_additional_headers=None):
        return req.url + "?" + "&".join(_param_to_quoted_query(k, v) for k, v in req.params.items())

    def _sign_rtmp_url(self, url, bucket_name, channel_name, expires, params):
        return url + "?" + "&".join(_param_to_quoted_query(k, v) for k, v in params.items())

    def auth_version(self):
        return ""


class StsAuth:
    """用于STS临时凭证访问。可以通过官方STS客户端获得临时密钥（AccessKeyId、AccessKeySecret）以及临时安全令牌（SecurityToken）。

    注意到临时凭证会在一段时间后过期，在此之前需要重新获取临时凭证，并更新 :class:`Bucket <aliyun_oss_x.Bucket>` 的 `auth` 成员变量为新
    的 `StsAuth` 实例。

    :param str access_key_id: 临时AccessKeyId
    :param str access_key_secret: 临时AccessKeySecret
    :param str security_token: 临时安全令牌(SecurityToken)
    :param str auth_version: 需要生成auth的版本，默认为AUTH_VERSION_1(v1)
    """

    def __init__(self, access_key_id: str, access_key_secret: str, security_token: str):
        logger.debug(
            "Init StsAuth: access_key_id: {0}, access_key_secret: ******, security_token: ******".format(access_key_id)
        )
        credentials_provider = StaticCredentialsProvider(access_key_id, access_key_secret, security_token)

        self.__auth = ProviderAuthV4(credentials_provider)

    def _sign_request(self, req, bucket_name, key):
        self.__auth._sign_request(req, bucket_name, key)

    def _sign_url(self, req, bucket_name, key, expires, in_additional_headers=None):
        return self.__auth._sign_url(req, bucket_name, key, expires, in_additional_headers)

    def _sign_rtmp_url(self, url, bucket_name, channel_name, expires, params):
        return self.__auth._sign_rtmp_url(url, bucket_name, channel_name, expires, params)

    def auth_version(self):
        return self.__auth.auth_version()


def _param_to_quoted_query(k, v):
    if v:
        return quote(k, "") + "=" + quote(v, "")
    else:
        return quote(k, "")


class ProviderAuthV4(AuthBase):
    """签名版本4，默认构造函数同父类AuthBase，需要传递credentials_provider
    与版本2的区别在：
    1. v4 签名规则引入了scope概念，SignToString(待签名串) 和 SigningKey （签名密钥）都需要包含 region信息
    2. 资源路径里的 / 不做转义。   query里的 / 需要转义为 %2F
    """

    def _sign_request(self, req, bucket_name, key, in_additional_headers=None):
        """把authorization放入req的header里面

        :param req: authorization信息将会加入到这个请求的header里面
        :type req: aliyun_oss_x.http.Request

        :param bucket_name: bucket名称
        :param key: OSS文件名
        :param in_additional_headers: 加入签名计算的额外header列表
        """
        if req.region is None:
            raise ClientError("The region should not be None in signature version 4.")

        credentials = self.credentials_provider.get_credentials()
        if credentials.get_security_token():
            req.headers[OSS_SECURITY_TOKEN] = credentials.get_security_token()

        now_datetime = datetime.now(timezone.utc)
        now_datetime_iso8601 = now_datetime.strftime("%Y%m%dT%H%M%SZ")
        now_date = now_datetime_iso8601[:8]
        req.headers["x-oss-date"] = now_datetime_iso8601
        req.headers["x-oss-content-sha256"] = "UNSIGNED-PAYLOAD"

        additional_signed_headers = self.__get_additional_signed_headers(in_additional_headers)
        credential = credentials.get_access_key_id() + "/" + self.__get_scope(now_date, req)
        signature = self.__make_signature(
            req, bucket_name, key, additional_signed_headers, credentials, now_datetime_iso8601
        )

        authorization = "OSS4-HMAC-SHA256 Credential={0}, Signature={1}".format(credential, signature)
        if additional_signed_headers:
            authorization = authorization + ", AdditionalHeaders={0}".format(";".join(additional_signed_headers))

        req.headers["authorization"] = authorization

    def _sign_url(self, req, bucket_name, key, expires, in_additional_headers=None) -> str:
        """返回一个签过名的URL

        :param req: 需要签名的请求
        :type req: aliyun_oss_x.http.Request

        :param bucket_name: bucket名称
        :param key: OSS文件名
        :param int expires: 返回的url将在`expires`秒后过期.
        :param in_additional_headers: 加入签名计算的额外header列表

        :return: a signed URL
        """
        credentials = self.credentials_provider.get_credentials()
        if credentials.get_security_token():
            req.params["x-oss-security-token"] = credentials.get_security_token()

        if in_additional_headers is None:
            in_additional_headers = set()

        additional_headers = self.__get_additional_headers(req, in_additional_headers)
        additional_headers = self.__get_additional_signed_headers(additional_headers)

        now_datetime = datetime.now(timezone.utc)
        now_datetime_iso8601 = now_datetime.strftime("%Y%m%dT%H%M%SZ")
        now_date = now_datetime_iso8601[:8]

        req.params["x-oss-date"] = now_datetime_iso8601
        req.params["x-oss-expires"] = str(expires)
        req.params["x-oss-signature-version"] = "OSS4-HMAC-SHA256"
        req.params["x-oss-credential"] = credentials.get_access_key_id() + "/" + self.__get_scope(now_date, req)
        if additional_headers:
            req.params["x-oss-additional-headers"] = self.__get_canonical_additional_signed_headers(additional_headers)

        signature = self.__make_signature(req, bucket_name, key, additional_headers, credentials, now_datetime_iso8601)
        req.params["x-oss-signature"] = signature
        return req.url + "?" + "&".join(_param_to_quoted_query(k, v) for k, v in req.params.items())

    def __make_signature(self, req, bucket_name, key, additional_signed_headers, credentials, date_time):
        canonical_request = self.__get_canonical_request_bytes(req, bucket_name, key, additional_signed_headers)
        string_to_sign = self.__get_string_to_sign_bytes(req, canonical_request, date_time)
        signing_key = self.__get_signing_key(req, credentials, date_time)
        signature = hmac.new(signing_key, to_bytes(string_to_sign), hashlib.sha256).hexdigest()
        # print("canonical_request:\n" + canonical_request)
        # print("string_to_sign:\n" + string_to_sign)
        logger.debug("Make signature: canonical_request = {0}".format(canonical_request))
        logger.debug("Make signature: string to be signed = {0}".format(string_to_sign))
        return signature

    def __get_additional_headers(self, req, in_additional_headers):
        # we add a header into additional_headers only if it is already in req's headers.

        additional_headers = set(h.lower() for h in in_additional_headers)
        keys_in_header = set(k.lower() for k in req.headers.keys())

        return additional_headers & keys_in_header

    def __get_additional_signed_headers(self, in_additional_headers):
        if in_additional_headers is None:
            return None
        headers = []
        for k in in_additional_headers:
            key = k.lower()
            if not (key.startswith("x-oss-") or DEFAULT_SIGNED_HEADERS.__contains__(key)):
                headers.append(key)
        headers.sort(key=lambda x: x[0])
        return headers

    def __get_canonical_uri(self, bucket_name, key):
        if bucket_name:
            encoded_uri = "/" + bucket_name + "/" + key
        else:
            encoded_uri = "/"
        return self.__v4_uri_encode(encoded_uri, True)

    def __param_to_query(self, k, v):
        if v:
            return k + "=" + v
        else:
            return k

    def __get_canonical_query(self, req):
        encoded_params = {}
        for param, value in req.params.items():
            encoded_params[self.__v4_uri_encode(param, False)] = self.__v4_uri_encode(value, False)

        if not encoded_params:
            return ""

        sorted_params = sorted(encoded_params.items(), key=lambda e: e[0])
        return "&".join(self.__param_to_query(k, v) for k, v in sorted_params)

    def __is_sign_header(self, key, additional_headers):
        if key is not None:
            if key.startswith("x-oss-"):
                return True

            if DEFAULT_SIGNED_HEADERS.__contains__(key):
                return True

            if additional_headers is not None and additional_headers.__contains__(key):
                return True

        return False

    def __get_canonical_headers(self, req, additional_headers):
        canon_headers = []
        for k, v in req.headers.items():
            lower_key = k.lower()
            if self.__is_sign_header(lower_key, additional_headers):
                canon_headers.append((lower_key, v))
        canon_headers.sort(key=lambda x: x[0])
        return "".join(v[0] + ":" + v[1] + "\n" for v in canon_headers)

    def __get_canonical_headers_bytes(self, req, additional_headers):
        canon_headers = []
        for k, v in req.headers.items():
            lower_key = k.lower()
            if self.__is_sign_header(lower_key, additional_headers):
                canon_headers.append((lower_key, v))
        canon_headers.sort(key=lambda x: x[0])
        return b"".join(to_bytes(v[0]) + b":" + to_bytes(v[1]) + b"\n" for v in canon_headers)

    def __get_canonical_additional_signed_headers(self, additional_headers):
        if additional_headers is None:
            return ""
        return ";".join(sorted(additional_headers))

    def __get_canonical_hash_payload(self, req):
        if req.headers.__contains__("x-oss-content-sha256"):
            return req.headers.get("x-oss-content-sha256", "")
        return "UNSIGNED-PAYLOAD"

    def __get_region(self, req):
        return req.cloudbox_id or req.region or ""

    def __get_product(self, req):
        return req.product

    def __get_scope(self, date, req):
        return date + "/" + self.__get_region(req) + "/" + self.__get_product(req) + "/aliyun_v4_request"

    def __get_canonical_request(self, req, bucket_name, key, additional_signed_headers):
        return (
            req.method
            + "\n"
            + self.__get_canonical_uri(bucket_name, key)
            + "\n"
            + self.__get_canonical_query(req)
            + "\n"
            + self.__get_canonical_headers(req, additional_signed_headers)
            + "\n"
            + self.__get_canonical_additional_signed_headers(additional_signed_headers)
            + "\n"
            + self.__get_canonical_hash_payload(req)
        )

    def __get_string_to_sign(self, req, canonical_request, date_time):
        date = date_time[:8]
        return (
            "OSS4-HMAC-SHA256"
            + "\n"
            + date_time
            + "\n"
            + self.__get_scope(date, req)
            + "\n"
            + hashlib.sha256(to_bytes(canonical_request)).hexdigest()
        )

    def __get_canonical_request_bytes(self, req, bucket_name, key, additional_signed_headers):
        return (
            to_bytes(req.method)
            + b"\n"
            + to_bytes(self.__get_canonical_uri(bucket_name, key))
            + b"\n"
            + to_bytes(self.__get_canonical_query(req))
            + b"\n"
            + self.__get_canonical_headers_bytes(req, additional_signed_headers)
            + b"\n"
            + to_bytes(self.__get_canonical_additional_signed_headers(additional_signed_headers))
            + b"\n"
            + to_bytes(self.__get_canonical_hash_payload(req))
        )

    def __get_string_to_sign_bytes(self, req, canonical_request_bytes, date_time):
        date = date_time[:8]
        return (
            "OSS4-HMAC-SHA256"
            + "\n"
            + date_time
            + "\n"
            + self.__get_scope(date, req)
            + "\n"
            + hashlib.sha256(canonical_request_bytes).hexdigest()
        )

    def __get_signing_key(self, req, credentials, date_time):
        date = date_time[:8]
        key_secret = "aliyun_v4" + credentials.get_access_key_secret()
        signing_date = hmac.new(to_bytes(key_secret), to_bytes(date), hashlib.sha256)
        signing_region = hmac.new(signing_date.digest(), to_bytes(self.__get_region(req)), hashlib.sha256)
        signing_product = hmac.new(signing_region.digest(), to_bytes(self.__get_product(req)), hashlib.sha256)
        signing_key = hmac.new(signing_product.digest(), to_bytes("aliyun_v4_request"), hashlib.sha256)
        return signing_key.digest()

    def __v4_uri_encode(self, raw_text, ignoreSlashes):
        raw_text = to_bytes(raw_text)

        res = ""
        for b in raw_text:
            if isinstance(b, int):
                c = chr(b)
            else:
                c = b

            if (
                (c >= "A" and c <= "Z")
                or (c >= "a" and c <= "z")
                or (c >= "0" and c <= "9")
                or c in ["_", "-", "~", "."]
            ):
                res += c
            elif ignoreSlashes is True and c == "/":
                res += c
            else:
                res += "%{0:02X}".format(ord(c))

        return res

    def auth_version(self):
        return AUTH_VERSION_4


class AuthV4(ProviderAuthV4):
    """签名版本4，与版本2的区别在：
    1. v4 签名规则引入了scope概念，SignToString(待签名串) 和 SigningKey （签名密钥）都需要包含 region信息
    2. 资源路径里的 / 不做转义。   query里的 / 需要转义为 %2F
    """

    def __init__(self, access_key_id, access_key_secret):
        credentials_provider = StaticCredentialsProvider(access_key_id.strip(), access_key_secret.strip())
        super(AuthV4, self).__init__(credentials_provider)


Auth = AuthV4
