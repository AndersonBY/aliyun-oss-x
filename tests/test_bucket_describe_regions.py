import unittest

import aliyun_oss_x

from .common import (
    OSS_ID,
    OSS_SECRET,
    OSS_ENDPOINT,
    OssTestCase,
)


class TestDescribeRegions(OssTestCase):
    def test_describe_regions_normal(self):
        service = aliyun_oss_x.Service(aliyun_oss_x.Auth(OSS_ID, OSS_SECRET), OSS_ENDPOINT)
        result = service.describe_regions()
        self.assertEqual(200, result.status)

        exist_region = False
        for r in result.regions:
            if "oss-cn-chengdu" == r.region:
                exist_region = True
        self.assertTrue(exist_region)

        exist_region = False
        result = service.describe_regions("oss-cn-chengdu")
        self.assertEqual(200, result.status)
        for r in result.regions:
            if "oss-cn-chengdu" == r.region:
                exist_region = True

        self.assertTrue(exist_region)

    def test_describe_regions_exception(self):
        try:
            service = aliyun_oss_x.Service(aliyun_oss_x.Auth(OSS_ID, OSS_SECRET), OSS_ENDPOINT)
            service.describe_regions("aaa")
        except aliyun_oss_x.exceptions.ServerError as e:
            self.assertEqual(e.code, "NoSuchRegion")


if __name__ == "__main__":
    unittest.main()
