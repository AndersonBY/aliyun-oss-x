# -*- coding: utf-8 -*-

import os
import aliyun_oss_x
from .common import *


class TestProxy(OssTestCase):
    def test_with_proxy(self):
        auth = aliyun_oss_x.Auth(OSS_ID, OSS_SECRET)
        bucket_name = self.OSS_BUCKET + "-test-proxy"

        proxies = {"http": "http://localhost:8888"}

        try:
            bucket = aliyun_oss_x.Bucket(auth, OSS_ENDPOINT, bucket_name, proxies=proxies)
            bucket.create_bucket(
                aliyun_oss_x.BUCKET_ACL_PRIVATE,
                aliyun_oss_x.models.BucketCreateConfig(aliyun_oss_x.BUCKET_STORAGE_CLASS_ARCHIVE),
            )
            self.assertTrue(False)
        except aliyun_oss_x.exceptions.RequestError as e:
            self.assertTrue(e.body.startswith("RequestError: HTTPConnectionPool(host='localhost', port=8888)"))
        except:
            self.assertTrue(False)

        try:
            service = aliyun_oss_x.Service(auth, OSS_ENDPOINT, proxies=proxies)
            service.list_buckets()
            self.assertTrue(False)
        except aliyun_oss_x.exceptions.RequestError as e:
            self.assertTrue(e.body.startswith("RequestError: HTTPConnectionPool(host='localhost', port=8888)"))
        except:
            self.assertTrue(False)

        bucket1 = aliyun_oss_x.Bucket(auth, OSS_ENDPOINT, bucket_name)
        bucket1.create_bucket()

        service1 = aliyun_oss_x.Service(auth, OSS_ENDPOINT)
        wait_meta_sync()
        self.retry_assert(
            lambda: bucket1.bucket_name in (b.name for b in service1.list_buckets(prefix=bucket1.bucket_name).buckets)
        )


if __name__ == "__main__":
    unittest.main()
