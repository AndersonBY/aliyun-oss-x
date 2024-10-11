import json
import time
import random
import datetime
import unittest

import aliyun_oss_x
from aliyun_oss_x.credentials import EcsRamRoleCredentialsProvider, EcsRamRoleCredentialsFetcher, EcsRamRoleCredential
from aliyunsdkcore import client
from aliyunsdksts.request.v20150401 import AssumeRoleRequest

from .common import (
    OSS_ID,
    OSS_SECRET,
    OSS_REGION,
    OSS_ENDPOINT,
    OSS_STS_ID,
    OSS_STS_KEY,
    OSS_STS_ARN,
    OssTestCase,
)


class TestCredentialsProvider(OssTestCase):
    def setUp(self):
        OssTestCase.setUp(self)
        self.auth_server_host = self.create_fake_ecs_credentials_url()
        self.endpoint = OSS_ENDPOINT
        self.bucket_name = self.OSS_BUCKET + "-test-ecs-ram-role"

    def tearDown(self):
        OssTestCase.tearDown(self)

    def create_fake_ecs_credentials_url(self):
        def get_fake_credentials_content(access_key_id, access_key_secret, role_arn, oss_region):
            clt = client.AcsClient(access_key_id, access_key_secret, oss_region)
            req = AssumeRoleRequest.AssumeRoleRequest()

            req.set_accept_format("json")
            req.set_RoleArn(role_arn)
            req.set_RoleSessionName("oss-python-sdk-fake-ecs-credentials-test")

            body = clt.do_action_with_exception(req)

            j = json.loads(body)
            credentials = dict()
            credentials["AccessKeyId"] = j["Credentials"]["AccessKeyId"]
            credentials["AccessKeySecret"] = j["Credentials"]["AccessKeySecret"]
            credentials["SecurityToken"] = j["Credentials"]["SecurityToken"]
            credentials["Expiration"] = j["Credentials"]["Expiration"]
            credentials["Code"] = "Success"
            if random.choice([True, False]):
                credentials["LastUpdated"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

            credentials = str(credentials)
            credentials_content = credentials.replace("'", '"')
            return credentials_content

        credentials_content = get_fake_credentials_content(OSS_STS_ID, OSS_STS_KEY, OSS_STS_ARN, OSS_REGION)
        tmp_object = "tmp-fake-ecs-credentials-obj"
        self.bucket.put_object(tmp_object, credentials_content)
        return self.bucket.sign_url("GET", tmp_object, 20)

    def test_auth(self):
        credentials_provider = EcsRamRoleCredentialsProvider(self.auth_server_host, 3, 10)
        object_name = "test-auth-ecs-ram-role-obj"

        credentials_provider = EcsRamRoleCredentialsProvider(self.auth_server_host, 3)

        credentials = credentials_provider.get_credentials()
        access_id = credentials.get_access_key_id()
        access_secret = credentials.get_access_key_secret()
        security_token = credentials.get_security_token()

        self.assertTrue(len(access_id) > 0)
        self.assertTrue(len(access_secret) > 0)
        self.assertTrue(len(security_token) > 0)

        bucket_name = self.OSS_BUCKET + "-test-auth-bucket"
        object_name = "test-auth-obj"
        auth4 = aliyun_oss_x.make_auth(OSS_ID, OSS_SECRET)

        test_bucket2 = aliyun_oss_x.Bucket(auth4, OSS_ENDPOINT, bucket_name)
        test_bucket2.put_object(object_name, "111")

        test_bucket2.delete_object(object_name)
        test_bucket2.delete_bucket()

    def test_sign_url(self):
        credentials_provider = EcsRamRoleCredentialsProvider(self.auth_server_host, 3, 10)
        provider_auth = aliyun_oss_x.ProviderAuthV4(credentials_provider)
        test_bucket = aliyun_oss_x.Bucket(provider_auth, self.endpoint, self.bucket_name)
        test_bucket.create_bucket()

        object_name = "test-ecs-role-url"
        file_name = self._prepare_temp_file_with_size(1024)

        url = test_bucket.sign_url("PUT", object_name, 60)
        result = test_bucket.put_object_with_url_from_file(url, file_name)
        self.assertEqual(result.status, 200)

        url = test_bucket.sign_url("GET", object_name, 60)

        result = test_bucket.get_object_with_url_to_file(url, file_name)
        self.assertEqual(result.status, 200)

        channel_name = "test-sign-rtmp-url"
        url = test_bucket.sign_rtmp_url(channel_name, "test.m3u8", 3600)
        self.assertTrue("security-token=" in url)

        test_bucket.delete_object(object_name)
        test_bucket.delete_bucket()

    def test_crypto_bucket(self):
        credentials_provider = EcsRamRoleCredentialsProvider(self.auth_server_host, 3, 10)
        provider_auth = aliyun_oss_x.ProviderAuthV4(credentials_provider)
        object_name = "test-auth-ecs-ram-role-obj"

        test_bucket = aliyun_oss_x.Bucket(provider_auth, self.endpoint, self.bucket_name)
        test_crypto_bucket = aliyun_oss_x.CryptoBucket(
            provider_auth, self.endpoint, self.bucket_name, crypto_provider=aliyun_oss_x.RsaProvider(key_pair)
        )
        test_crypto_bucket.create_bucket()

        content = b"1" * 1025
        test_crypto_bucket.put_object(object_name, content)
        result1 = test_crypto_bucket.get_object(object_name)
        content1 = result1.read()
        self.assertEqual(content, content1)

        result2 = test_bucket.get_object(object_name)
        content2 = result2
        self.assertNotEqual(content, content2)

        test_bucket.delete_object(object_name)
        test_bucket.delete_bucket()

    def test_ecs_ram_role_credentials_expire(self):
        from aliyun_oss_x.credentials import EcsRamRoleCredential

        t = int(time.mktime(time.localtime()))
        credentials = EcsRamRoleCredential("test-id", "test-secret", "test-token", t + 9, 10, 0.4)
        self.assertEqual("test-id", credentials.get_access_key_id())
        self.assertEqual("test-secret", credentials.get_access_key_secret())
        self.assertEqual("test-token", credentials.get_security_token())
        self.assertFalse(credentials.will_soon_expire())
        time.sleep(10 * 0.4 + 1)
        self.assertTrue(credentials.will_soon_expire())

    def test_ecs_ram_role_credentials_fetcher(self):
        fetcher = EcsRamRoleCredentialsFetcher("err_host")
        self.assertRaises(aliyun_oss_x.exceptions.ClientError, fetcher.fetch, 3)

        fetcher = EcsRamRoleCredentialsFetcher("http://www.aliyun.com")
        self.assertRaises(aliyun_oss_x.exceptions.ClientError, fetcher.fetch, 3)

        fetcher = EcsRamRoleCredentialsFetcher(self.auth_server_host)
        fetcher.fetch(retry_times=3, timeout=5)

    def test_ecs_ram_role_credentials_provider(self):
        class FakeFetcher:
            def __init__(self, expiration, duration, factor):
                self.expiration = expiration
                self.duration = duration
                self.factor = factor

            def fetch(self, retry_times=3, timeout=10):
                return EcsRamRoleCredential(
                    "test-id", "test-secret", "test-token", self.expiration, self.duration, self.factor
                )

        class FakeFetcherErr:
            def fetch(self, retry_times=3, timeout=10):
                raise aliyun_oss_x.exceptions.ClientError("fake error")

        provider = EcsRamRoleCredentialsProvider(self.auth_server_host)
        self.assertIsNone(provider.credentials)

        t = int(time.mktime(time.localtime()))
        provider.fetcher = FakeFetcher(t + 9, 10, 0.4)
        credentials1 = provider.get_credentials()
        credentials2 = provider.get_credentials()
        self.assertEqual(t + 9, credentials1.expiration)
        self.assertEquals(credentials1, credentials2)
        self.assertFalse(credentials2.will_soon_expire())
        time.sleep(10 * 0.4 + 1)
        self.assertTrue(credentials2.will_soon_expire())
        credentials3 = provider.get_credentials()
        self.assertNotEquals(credentials2, credentials3)

        provider = EcsRamRoleCredentialsProvider(self.auth_server_host)
        credentials1 = provider.get_credentials()
        self.assertIsNotNone(credentials1)
        provider.fetcher = FakeFetcherErr()
        self.assertRaises(aliyun_oss_x.exceptions.ClientError, provider.fetcher.fetch)
        credentials2 = provider.get_credentials()
        self.assertEqual(credentials1, credentials2)


if __name__ == "__main__":
    unittest.main()
