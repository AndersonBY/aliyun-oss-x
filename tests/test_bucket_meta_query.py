import time
import unittest

import aliyun_oss_x
from aliyun_oss_x.models import MetaQuery, AggregationsRequest

from .common import (
    OSS_ID,
    OSS_ENDPOINT,
    OSS_SECRET,
    OssTestCase,
)


class TestBucketMetaQuery(OssTestCase):
    def setUp(self):
        OssTestCase.setUp(self)

    def tearDown(self):
        try:
            OssTestCase.tearDown(self)
        except Exception:
            pass

    def test_1_bucket_meta_query(self):
        if self.bucket is None:
            raise Exception("bucket is None")
        key = "a.txt"
        self.bucket.put_object(key, "content")
        result = self.bucket.open_bucket_meta_query()
        self.assertEqual(200, result.status)
        key = "b.txt"
        self.bucket.put_object(key, "content bbbbbbb")

        while True:
            time.sleep(5)
            get_result = self.bucket.get_bucket_meta_query_status()
            if get_result.state == "Running":
                do_meta_query_request = MetaQuery(
                    "", 2, '{"Field": "Size","Value": "1048576","Operation": "lt"}', "Size", "asc"
                )
                result = self.bucket.do_bucket_meta_query(do_meta_query_request)

                # if result.files.__len__() <= 0:
                # continue
                # self.assertEqual(200, result.status)
                # self.assertEqual('a.txt', result.files[0].file_name)
                # self.assertIsNotNone(result.files[0].etag)
                # self.assertIsNotNone(result.files[0].oss_object_type)
                # self.assertIsNotNone(result.files[0].oss_storage_class)
                # self.assertIsNotNone(result.files[0].oss_crc64)
                # self.assertIsNotNone(result.files[0].object_acl)
                # self.assertEqual('b.txt', result.files[1].file_name)
                # self.assertIsNotNone(result.files[1].etag)
                # self.assertIsNotNone(result.files[1].oss_object_type)
                # self.assertIsNotNone(result.files[1].oss_storage_class)
                # self.assertIsNotNone(result.files[1].oss_crc64)
                # self.assertIsNotNone(result.files[1].object_acl)
                break

        result = self.bucket.close_bucket_meta_query()
        self.assertEqual(200, result.status)

    def test_2_bucket_meta_query_aggregation(self):
        auth = aliyun_oss_x.Auth(OSS_ID, OSS_SECRET)
        dest_bucket_name = self.OSS_BUCKET + "-test-meta-query"
        dest_bucket = aliyun_oss_x.Bucket(auth, OSS_ENDPOINT, dest_bucket_name)
        dest_bucket.create_bucket()

        key = "c.txt"
        dest_bucket.put_object(key, "content  ccccc")
        result = dest_bucket.open_bucket_meta_query()
        self.assertEqual(200, result.status)
        key = "d.txt"
        dest_bucket.put_object(key, "content dddddd")
        while True:
            time.sleep(5)
            get_result = dest_bucket.get_bucket_meta_query_status()
            if get_result.state == "Running":
                aggregations1 = AggregationsRequest(field="Size", operation="sum")
                aggregations2 = AggregationsRequest(field="Size", operation="max")
                do_meta_query_request = MetaQuery(
                    max_results=2,
                    query='{"Field": "Size","Value": "1048576","Operation": "lt"}',
                    sort="Size",
                    order="asc",
                    aggregations=[aggregations1, aggregations2],
                )
                result = dest_bucket.do_bucket_meta_query(do_meta_query_request)

                # if result.files.__len__() <= 0:
                # continue
                # self.assertEqual(200, result.status)
                # self.assertEqual('Size', result.aggregations[0].field)
                # self.assertEqual('sum', result.aggregations[0].operation)
                # self.assertEqual('Size', result.aggregations[1].field)
                # self.assertEqual('max', result.aggregations[1].operation)
                break
        result = dest_bucket.close_bucket_meta_query()
        self.assertEqual(200, result.status)

        dest_bucket.delete_object("c.txt")
        dest_bucket.delete_object("d.txt")
        dest_bucket.delete_bucket()


if __name__ == "__main__":
    unittest.main()
