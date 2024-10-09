import unittest

import aliyun_oss_x

from .common import OssTestCase


class TestBucketResourceGroup(OssTestCase):
    def test_bucket_resource_group_normal(self):
        if self.bucket is None:
            raise Exception("bucket is None")

        get_result = self.bucket.get_bucket_resource_group()
        print(get_result.status)
        self.assertEqual(200, get_result.status)

        result = self.bucket.put_bucket_resource_group(get_result.resource_group_id)
        self.assertEqual(200, result.status)

    def test_bucket_worm_illegal(self):
        if self.bucket is None:
            raise Exception("bucket is None")
        try:
            self.bucket.put_bucket_resource_group("rg-xxxxxx")
        except aliyun_oss_x.exceptions.ServerError as e:
            self.assertEqual(e.details["Code"], "ResourceGroupIdPreCheckError")


if __name__ == "__main__":
    unittest.main()
