# -*- coding: utf-8 -*-

import unittest
import aliyun_oss_x
import os


class TestResumable(unittest.TestCase):
    def test_determine_part_size(self):
        self.assertEqual(
            aliyun_oss_x.determine_part_size(aliyun_oss_x.defaults.part_size + 1), aliyun_oss_x.defaults.part_size
        )

        self.assertEqual(aliyun_oss_x.determine_part_size(1), 1)
        self.assertEqual(aliyun_oss_x.determine_part_size(1, aliyun_oss_x.defaults.part_size + 1), 1)

        n = 10000
        size = (aliyun_oss_x.defaults.part_size + 1) * n
        part_size = aliyun_oss_x.determine_part_size(size)
        self.assertEqual(part_size, aliyun_oss_x.defaults.part_size * 2)

        n = 10000
        size = (aliyun_oss_x.defaults.part_size * n) + 5
        part_size = aliyun_oss_x.determine_part_size(size)
        self.assertTrue((n * part_size) > size)
        self.assertTrue(aliyun_oss_x.defaults.part_size < part_size)

    def test_resumable_store_dir(self):
        root = "./"
        store_dir = "test-resumable-store-dir"
        path = root + store_dir

        self.assertFalse(os.path.exists(path))
        store = aliyun_oss_x.ResumableStore(root, store_dir)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.path.isdir(path))

        os.rmdir(path)


if __name__ == "__main__":
    unittest.main()
