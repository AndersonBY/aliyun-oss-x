import unittest

import aliyun_oss_x

from .common import (
    OSS_ID,
    OSS_SECRET,
    OSS_ENDPOINT,
    OssTestCase,
)


class TestExceptionEC(OssTestCase):
    def setUp(self):
        OssTestCase.setUp(self)

    def tearDown(self):
        try:
            OssTestCase.tearDown(self)
        except Exception:
            pass

    def test_1_exception_normal(self):
        key = "a.txt"
        try:
            self.bucket.get_object(key)
        except aliyun_oss_x.exceptions.ServerError as e:
            self.assertEqual(e.headers.get("x-oss-ec"), "0026-00000001")
            self.assertEqual(e.ec, "0026-00000001")

    def test_2_exception_head(self):
        key = "a.txt"
        try:
            self.bucket.get_object_meta(key)
        except aliyun_oss_x.exceptions.OssError as e:
            self.assertEqual(e.ec, "0026-00000001")
            self.assertEqual(e.headers.get("x-oss-ec"), "0026-00000001")

    def test_3_exception_head_err(self):
        # 模拟head请求下的签名错误
        auth = aliyun_oss_x.AuthV4(OSS_ID, OSS_SECRET)
        bucket = aliyun_oss_x.Bucket(auth, OSS_ENDPOINT, self.OSS_BUCKET, region="cn-hangzhou-test-1")
        key = "a.txt"

        try:
            bucket.head_object(key)
        except aliyun_oss_x.exceptions.OssError as e:
            self.assertEqual(e.ec, "0002-00000226")
            self.assertEqual(e.headers.get("x-oss-ec"), "0002-00000226")
            self.assertEqual(e.code, "InvalidArgument")
            self.assertEqual(e.message, "Invalid signing region in Authorization header.")


if __name__ == "__main__":
    unittest.main()
