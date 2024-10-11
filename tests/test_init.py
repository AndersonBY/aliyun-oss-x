import logging
import unittest

import aliyun_oss_x

from .common import OssTestCase


class TestInit(OssTestCase):
    def test_set_logger(self):
        aliyun_oss_x.set_stream_logger("aliyun_oss_x", logging.DEBUG)
        self.assertTrue(aliyun_oss_x.logger.name, "aliyun_oss_x")
        self.assertTrue(aliyun_oss_x.logger.level, logging.DEBUG)

        log_file_path = self.random_filename()
        aliyun_oss_x.set_file_logger(log_file_path, "aliyun_oss_x", logging.INFO)
        self.assertTrue(aliyun_oss_x.logger.name, "aliyun_oss_x")
        self.assertTrue(aliyun_oss_x.logger.level, logging.INFO)
        aliyun_oss_x.logger.info("hello, aliyun_oss_x")

        with open(log_file_path, "rb") as f:
            self.assertTrue("hello, aliyun_oss_x" in f.read().decode())

        aliyun_oss_x.set_stream_logger("aliyun_oss_x", logging.CRITICAL)
        aliyun_oss_x.set_file_logger(log_file_path, "aliyun_oss_x", logging.CRITICAL)


if __name__ == "__main__":
    unittest.main()
