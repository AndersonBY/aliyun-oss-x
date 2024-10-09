import unittest

import aliyun_oss_x

from .common import OssTestCase


class TestBucketWorm(OssTestCase):
    def test_bucke_worm_normal(self):
        if self.bucket is None:
            raise Exception("bucket is None")

        init_result = self.bucket.init_bucket_worm(1)
        worm_id = init_result.worm_id
        self.assertIsNotNone(init_result.request_id)

        get_result = self.bucket.get_bucket_worm()
        self.assertIsNotNone(get_result.request_id)
        self.assertEqual(worm_id, get_result.worm_id)
        self.assertEqual("InProgress", get_result.state)
        self.assertEqual(1, get_result.retention_period_days)
        self.assertIsNotNone(get_result.creation_date)

        complete_reuslt = self.bucket.complete_bucket_worm(worm_id)
        self.assertIsNotNone(complete_reuslt.request_id)
        get_result = self.bucket.get_bucket_worm()
        self.assertEqual(worm_id, get_result.worm_id)
        self.assertEqual("Locked", get_result.state)
        self.assertEqual(1, get_result.retention_period_days)
        self.assertIsNotNone(get_result.creation_date)

        extend_result = self.bucket.extend_bucket_worm(worm_id, 2)
        self.assertIsNotNone(extend_result.request_id)
        get_result = self.bucket.get_bucket_worm()
        self.assertEqual(worm_id, get_result.worm_id)
        self.assertEqual("Locked", get_result.state)
        self.assertEqual(2, get_result.retention_period_days)
        self.assertIsNotNone(get_result.creation_date)

    def test_abort_bucket_worm(self):
        if self.bucket is None:
            raise Exception("bucket is None")

        self.bucket.init_bucket_worm(1)
        abort_result = self.bucket.abort_bucket_worm()
        self.assertIsNotNone(abort_result.request_id)

        init_result = self.bucket.init_bucket_worm(1)
        worm_id = init_result.worm_id

        self.bucket.complete_bucket_worm(worm_id)
        self.assertRaises(aliyun_oss_x.exceptions.WORMConfigurationLocked, self.bucket.abort_bucket_worm)

    def test_bucket_worm_illegal(self):
        if self.bucket is None:
            raise Exception("bucket is None")

        self.assertRaises(aliyun_oss_x.exceptions.NoSuchWORMConfiguration, self.bucket.get_bucket_worm)

        init_result = self.bucket.init_bucket_worm(1)
        worm_id = init_result.worm_id

        self.assertRaises(aliyun_oss_x.exceptions.InvalidWORMConfiguration, self.bucket.extend_bucket_worm, worm_id, 2)


if __name__ == "__main__":
    unittest.main()
