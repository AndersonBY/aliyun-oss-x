import unittest

import aliyun_oss_x

from .common import OssTestCase


class TestBucketTransferAccelerat(OssTestCase):
    def test_bucket_transfer_acceleration_normal(self):
        if self.bucket is None:
            raise Exception("bucket is None")

        result = self.bucket.put_bucket_transfer_acceleration("true")
        self.assertEqual(200, result.status)

        get_result = self.bucket.get_bucket_transfer_acceleration()
        self.assertEqual("true", get_result.enabled)

    def test_bucket_worm_illegal(self):
        if self.bucket is None:
            raise Exception("bucket is None")

        self.assertRaises(
            aliyun_oss_x.exceptions.NoSuchTransferAccelerationConfiguration,
            self.bucket.get_bucket_transfer_acceleration,
        )


if __name__ == "__main__":
    unittest.main()
