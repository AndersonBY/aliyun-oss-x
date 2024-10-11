import os
import unittest

import aliyun_oss_x
from aliyun_oss_x.compat import to_bytes

from .common import (
    OssTestCase,
    random_bytes,
    random_string,
)


class TestChinese(OssTestCase):
    def test_unicode_content(self):
        key = self.random_key()
        content = "几天后，阿里巴巴为侄子和马尔佳娜举行了隆重的婚礼。"

        self.bucket.put_object(key, content)
        self.assertEqual(self.bucket.get_object(key).read(), content.encode("utf-8"))

    def test_put_get_list_delete(self):
        for key in ["中文!@#$%^&*()-=文件\x0c-1.txt", "中文!@#$%^&*()-=文件\x0c-1.txt"]:
            content = "中文内容"

            self.bucket.put_object(key, content)
            self.assertEqual(self.bucket.get_object(key).read(), to_bytes(content))

            self.assertTrue(key in list(info.key for info in aliyun_oss_x.ObjectIterator(self.bucket, prefix="中文")))

            self.bucket.delete_object(key)

    def test_batch_delete_objects(self):
        for key in ["中文!@#$%^&*()-=文件\x0c-2.txt", "中文!@#$%^&*()-=文件\x0c-3.txt", "<hello>"]:
            content = "中文内容"

            self.bucket.put_object(key, content)
            result = self.bucket.batch_delete_objects([key])
            self.assertEqual(result.deleted_keys[0], key)

            self.assertTrue(not self.bucket.object_exists(key))

    def test_local_file(self):
        key = self.random_key("文件!@#$%^&*()-=\x0d\x0e\x7f名")
        content = random_bytes(32) + "内容\x0d\x0e\7F是中文\x01".encode("utf-8")

        self.bucket.put_object(key, content)

        key2 = random_string(16)

        self.bucket.get_object_to_file(key, "中文本地文件名.txt")
        self.bucket.put_object_from_file(key2, "中文本地文件名.txt")

        self.assertEqual(self.bucket.get_object(key2).read(), content)

        os.remove("中文本地文件名.txt")
        self.bucket.delete_object(key)
        self.bucket.delete_object(key2)

    def test_get_symlink(self):
        key = "中文!@#$%^&*()-=文件\x0c-1.txt"
        symlink = "中文!@#$%^&*()-=文件\x0c-2.txt"
        content = "中文内容"

        self.bucket.put_object(key, content)
        self.bucket.put_symlink(key, symlink)

        result = self.bucket.get_symlink(symlink)
        self.assertEqual(result.target_key, key)

        self.bucket.delete_object(symlink)
        self.bucket.delete_object(key)


if __name__ == "__main__":
    unittest.main()
