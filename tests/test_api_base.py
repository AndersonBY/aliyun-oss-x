import sys
import unittest
import socket

import aliyun_oss_x

from .common import (
    OSS_ID,
    OSS_CNAME,
    OSS_SECRET,
    OSS_REGION,
    OSS_ENDPOINT,
    OssTestCase,
    random_string,
)


class TestApiBase(OssTestCase):
    if OSS_CNAME:

        def test_cname_bucket(self):
            bucket = aliyun_oss_x.Bucket(
                aliyun_oss_x.Auth(OSS_ID, OSS_SECRET), OSS_CNAME, self.OSS_BUCKET, is_cname=True, region=OSS_REGION
            )
            bucket.get_bucket_acl()

        def test_cname_object(self):
            bucket = aliyun_oss_x.Bucket(
                aliyun_oss_x.Auth(OSS_ID, OSS_SECRET), OSS_CNAME, self.OSS_BUCKET, is_cname=True, region=OSS_REGION
            )
            bucket.put_object("hello.txt", "hello world")

    def test_https(self):
        bucket_name = random_string(63)
        bucket = aliyun_oss_x.Bucket(
            aliyun_oss_x.AnonymousAuth(), OSS_ENDPOINT.replace("http://", "https://"), bucket_name, region=OSS_REGION
        )
        self.assertRaises(aliyun_oss_x.exceptions.NoSuchBucket, bucket.get_object, "hello.txt")

    # 只是为了测试，请不要用IP访问OSS，除非你是在VPC环境下。
    def test_ip(self):
        bucket_name = random_string(63)
        ip = socket.gethostbyname(OSS_ENDPOINT.replace("https://", "").replace("http://", ""))

        bucket = aliyun_oss_x.Bucket(aliyun_oss_x.AnonymousAuth(), ip, bucket_name, region=OSS_REGION)
        self.assertRaises(aliyun_oss_x.exceptions.NoSuchBucket, bucket.get_object, "hello.txt")

    def test_invalid_bucket_name(self):
        bucket_name = random_string(64)
        self.assertRaises(
            aliyun_oss_x.exceptions.ClientError,
            aliyun_oss_x.Bucket,
            aliyun_oss_x.AnonymousAuth(),
            OSS_ENDPOINT,
            bucket_name,
        )

    def test_check_endpoint1(self):
        endpoint = "www.aliyuncs.com"
        aliyun_oss_x.Bucket(aliyun_oss_x.AnonymousAuth(), endpoint, "test-bucket")

    def test_check_endpoint(self):
        from aliyun_oss_x.api._utils import _normalize_endpoint

        endpoint = "www.aliyuncs.com/?x=123#segemnt "
        aliyun_oss_x.Bucket(aliyun_oss_x.AnonymousAuth(), endpoint, "test-bucket")
        normalized_endpoint = _normalize_endpoint(endpoint)
        self.assertEqual("http://www.aliyuncs.com", normalized_endpoint)

        endpoint = "http://www.aliyuncs.com/?x=123#segemnt "
        aliyun_oss_x.Bucket(aliyun_oss_x.AnonymousAuth(), endpoint, "test-bucket")
        normalized_endpoint = _normalize_endpoint(endpoint)
        self.assertEqual("http://www.aliyuncs.com", normalized_endpoint)

        endpoint = "http://192.168.1.1:3182/?x=123#segemnt "
        aliyun_oss_x.Bucket(aliyun_oss_x.AnonymousAuth(), endpoint, "test-bucket")
        normalized_endpoint = _normalize_endpoint(endpoint)
        self.assertEqual("http://192.168.1.1:3182", normalized_endpoint)

        endpoint = "http://www.aliyuncs.com:80/?x=123#segemnt "
        aliyun_oss_x.Bucket(aliyun_oss_x.AnonymousAuth(), endpoint, "test-bucket")
        normalized_endpoint = _normalize_endpoint(endpoint)
        self.assertEqual("http://www.aliyuncs.com:80", normalized_endpoint)

        endpoint = "https://www.aliyuncs.com:443/?x=123#segemnt"
        aliyun_oss_x.Bucket(aliyun_oss_x.AnonymousAuth(), endpoint, "test-bucket")
        normalized_endpoint = _normalize_endpoint(endpoint)
        self.assertEqual("https://www.aliyuncs.com:443", normalized_endpoint)

        endpoint = "https://www.aliyuncs.com:443"
        aliyun_oss_x.Bucket(aliyun_oss_x.AnonymousAuth(), endpoint, "test-bucket")
        normalized_endpoint = _normalize_endpoint(endpoint)
        self.assertEqual("https://www.aliyuncs.com:443", normalized_endpoint)

        self.assertRaises(
            aliyun_oss_x.exceptions.ClientError,
            aliyun_oss_x.Bucket,
            aliyun_oss_x.AnonymousAuth(),
            OSS_ENDPOINT + "\\",
            "test-bucket",
        )

    def test_whitespace(self):
        bucket = aliyun_oss_x.Bucket(aliyun_oss_x.Auth(OSS_ID, " " + OSS_SECRET + " "), OSS_ENDPOINT, self.OSS_BUCKET)
        bucket.get_bucket_acl()

        bucket = aliyun_oss_x.Bucket(aliyun_oss_x.Auth(OSS_ID, OSS_SECRET), " " + OSS_ENDPOINT + " ", self.OSS_BUCKET)
        bucket.get_bucket_acl()

        bucket = aliyun_oss_x.Bucket(aliyun_oss_x.Auth(OSS_ID, OSS_SECRET), OSS_ENDPOINT, " " + self.OSS_BUCKET + " ")
        bucket.get_bucket_acl()

    if sys.version_info >= (3, 3):

        def test_user_agent(self):
            app = "fantastic-tool"

            assert_found = False

            def do_request(session_self, req, timeout):
                if assert_found:
                    self.assertTrue(req.headers["User-Agent"].find(app) >= 0)
                else:
                    self.assertTrue(req.headers["User-Agent"].find(app) < 0)

                raise aliyun_oss_x.exceptions.ClientError("intentional")

            from unittest.mock import patch

            with patch.object(aliyun_oss_x.Session, "do_request", side_effect=do_request, autospec=True):
                # 不加 app_name
                assert_found = False
                if self.bucket is None:
                    raise Exception("bucket is None")
                self.assertRaises(aliyun_oss_x.exceptions.ClientError, self.bucket.get_bucket_acl)

                service = aliyun_oss_x.Service(aliyun_oss_x.Auth(OSS_ID, OSS_SECRET), OSS_ENDPOINT)
                self.assertRaises(aliyun_oss_x.exceptions.ClientError, service.list_buckets)

                # 加app_name
                assert_found = True
                bucket = aliyun_oss_x.Bucket(
                    aliyun_oss_x.Auth(OSS_ID, OSS_SECRET), OSS_ENDPOINT, self.OSS_BUCKET, app_name=app
                )
                self.assertRaises(aliyun_oss_x.exceptions.ClientError, bucket.get_bucket_acl)

                service = aliyun_oss_x.Service(aliyun_oss_x.Auth(OSS_ID, OSS_SECRET), OSS_ENDPOINT, app_name=app)
                self.assertRaises(aliyun_oss_x.exceptions.ClientError, service.list_buckets)


if __name__ == "__main__":
    unittest.main()
