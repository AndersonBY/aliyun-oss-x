# -*- coding: utf-8 -*-

import os
import copy
import random
import tempfile
import unittest
from mock import patch
from typing import Callable

import aliyun_oss_x
from functools import partial

from .common import (
    OssTestCase,
    random_bytes,
    NonlocalObject,
)


class SizedFileAdapterForMock:
    def __init__(self, file_object, size, content_length=None):
        self.f = aliyun_oss_x.utils.SizedFileAdapter(file_object, size)
        self.content_length = content_length
        self.request_id = "fake-request-id"

    def read(self, amt=None):
        return self.f.read(amt)

    @property
    def len(self):
        return self.f.len

    @property
    def server_crc(self):
        return None

    @property
    def client_crc(self):
        return None


orig_get_object = aliyun_oss_x.Bucket.get_object


def mock_get_object(
    b,
    k,
    byte_range=None,
    headers=None,
    progress_callback: Callable[[int, int | None], None] | None = None,
    process=None,
    content_length=None,
    params=None,
):
    res = orig_get_object(b, k, byte_range, headers, progress_callback, process, params)

    return SizedFileAdapterForMock(res, 50, content_length)


def modify_one(store, store_key, r, key=None, value=None):
    r[key] = value
    store.put(store_key, r)


class TestDownload(OssTestCase):
    def __prepare(self, bucket, file_size, suffix=""):
        content = random_bytes(file_size)
        key = self.random_key(suffix)
        filename = self.random_filename()
        bucket.put_object(key, content)
        return key, filename, content

    def __record(self, key, filename, store=None):
        store = store or aliyun_oss_x.resumable.make_download_store()
        store_key = store.make_store_key(self.bucket.bucket_name, key, os.path.abspath(filename))
        return store.get(store_key)

    def __test_normal(self, file_size):
        bucket = random.choice([self.bucket, self.rsa_crypto_bucket, self.kms_crypto_bucket])
        key, filename, content = self.__prepare(bucket, file_size)
        aliyun_oss_x.resumable_download(bucket, key, filename)

        self.assertFileContent(filename, content)

    def test_small_file(self):
        aliyun_oss_x.defaults.multiget_threshold = 1024 * 1024
        self.__test_normal(1023)

    def test_large_file_single_threaded(self):
        aliyun_oss_x.defaults.multiget_threshold = 1024 * 1024
        aliyun_oss_x.defaults.multiget_part_size = 1024 * 1024 + 1
        aliyun_oss_x.defaults.multiget_num_threads = 1

        self.__test_normal(2 * 1024 * 1024 + 1)

    def test_large_multi_threaded(self):
        # """多线程，线程数少于分片数"""

        aliyun_oss_x.defaults.multiget_threshold = 1024 * 1024
        aliyun_oss_x.defaults.multiget_part_size = 100 * 1024
        aliyun_oss_x.defaults.multiget_num_threads = 7

        self.__test_normal(2 * 1024 * 1024)

    def test_large_many_threads(self):
        # """线程数多余分片数"""

        aliyun_oss_x.defaults.multiget_threshold = 1024 * 1024
        aliyun_oss_x.defaults.multiget_part_size = 100 * 1024
        aliyun_oss_x.defaults.multiget_num_threads = 10

        self.__test_normal(512 * 1024 - 1)

    def __test_resume(self, file_size, failed_parts, modify_func_record=None):
        total = NonlocalObject(0)
        bucket = random.choice([self.bucket, self.rsa_crypto_bucket, self.kms_crypto_bucket])

        orig_download_part = aliyun_oss_x.resumable._ResumableDownloader._ResumableDownloader__download_part

        def mock_download_part(self, part, failed_parts=None):
            if part.part_number in failed_parts:
                raise RuntimeError("Fail download_part for part: {0}".format(part.part_number))
            else:
                total.var += 1
                orig_download_part(self, part)

        key, filename, content = self.__prepare(bucket, file_size)

        with patch.object(
            aliyun_oss_x.resumable._ResumableDownloader,
            "_ResumableDownloader__download_part",
            side_effect=partial(mock_download_part, failed_parts=failed_parts),
            autospec=True,
        ):
            self.assertRaises(RuntimeError, aliyun_oss_x.resumable_download, bucket, key, filename)

        store = aliyun_oss_x.resumable.make_download_store()
        store_key = store.make_store_key(bucket.bucket_name, key, os.path.abspath(filename))
        record = store.get(store_key)

        tmp_file = filename + record["tmp_suffix"]
        self.assertTrue(os.path.exists(tmp_file))
        self.assertTrue(not os.path.exists(filename))

        with patch.object(
            aliyun_oss_x.resumable._ResumableDownloader,
            "_ResumableDownloader__download_part",
            side_effect=partial(mock_download_part, failed_parts=[]),
            autospec=True,
        ):
            aliyun_oss_x.resumable_download(bucket, key, filename)

        self.assertEqual(total.var, aliyun_oss_x.utils.how_many(file_size, aliyun_oss_x.defaults.multiget_part_size))
        self.assertTrue(not os.path.exists(tmp_file))
        self.assertFileContent(filename, content)

    def test_resume_hole_start(self):
        # """第一个part失败"""

        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 500
        aliyun_oss_x.defaults.multiget_num_threads = 3
        aliyun_oss_x.defaults.min_part_size = 500

        self.__test_resume(500 * 10 + 16, [1])

    def test_resume_hole_end(self):
        # """最后一个part失败"""

        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 500
        aliyun_oss_x.defaults.multiget_num_threads = 2
        aliyun_oss_x.defaults.min_part_size = 500

        self.__test_resume(500 * 10 + 16, [11])

    def test_resume_hole_mid(self):
        # """中间part失败"""

        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 500
        aliyun_oss_x.defaults.multiget_num_threads = 3
        aliyun_oss_x.defaults.min_part_size = 500

        self.__test_resume(500 * 10 + 16, [3])

    # 模拟rename出错的情况
    def test_resume_rename_failed(self):
        bucket = random.choice([self.bucket, self.rsa_crypto_bucket, self.kms_crypto_bucket])
        size = 500 * 10
        part_size = 499

        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = part_size
        aliyun_oss_x.defaults.multiget_num_threads = 3
        aliyun_oss_x.defaults.min_part_size = 499

        key, filename, content = self.__prepare(bucket, size)

        with patch.object(os, "rename", side_effect=RuntimeError(), autospec=True):
            self.assertRaises(RuntimeError, aliyun_oss_x.resumable_download, bucket, key, filename)

        r = self.__record(key, filename)

        # assert record fields are valid
        head_object_result = bucket.head_object(key)

        self.assertEqual(r["size"], size)
        self.assertEqual(r["mtime"], head_object_result.last_modified)
        self.assertEqual(r["etag"], head_object_result.etag)

        self.assertEqual(r["bucket"], bucket.bucket_name)
        self.assertEqual(r["key"], key)
        self.assertEqual(r["part_size"], part_size)

        self.assertTrue(os.path.exists(filename + r["tmp_suffix"]))
        self.assertFileContent(filename + r["tmp_suffix"], content)

        self.assertTrue(not os.path.exists(filename))

        self.assertEqual(r["file_path"], os.path.abspath(filename))

        self.assertEqual(len(r["parts"]), aliyun_oss_x.utils.how_many(size, part_size))

        parts = sorted(r["parts"], key=lambda p: p["part_number"])
        for i, p in enumerate(parts):
            self.assertEqual(p["part_number"], i + 1)
            self.assertEqual(p["start"], part_size * i)
            self.assertEqual(p["end"], min(part_size * (i + 1), size))

        with patch.object(
            aliyun_oss_x.resumable._ResumableDownloader,
            "_ResumableDownloader__download_part",
            side_effect=RuntimeError(),
            autospec=True,
        ):
            aliyun_oss_x.resumable_download(bucket, key, filename)

        self.assertTrue(not os.path.exists(filename + r["tmp_suffix"]))
        self.assertFileContent(filename, content)
        self.assertEqual(self.__record(key, filename), None)

    def __test_insane_record(self, file_size, modify_record_func, old_tmp_exists=True):
        bucket = random.choice([self.bucket, self.rsa_crypto_bucket, self.kms_crypto_bucket])

        orig_rename = os.rename

        obj = NonlocalObject({})

        key, filename, content = self.__prepare(bucket, file_size)

        def mock_rename(src, dst):
            obj.var = self.__record(key, filename)
            orig_rename(src, dst)

        # 这个地方模拟rename报错
        with patch.object(os, "rename", side_effect=RuntimeError(), autospec=True):
            self.assertRaises(RuntimeError, aliyun_oss_x.resumable_download, bucket, key, filename)

        store = aliyun_oss_x.resumable.make_download_store()
        store_key = store.make_store_key(bucket.bucket_name, key, os.path.abspath(filename))
        r = store.get(store_key)

        # 修改record文件
        modify_record_func(store, store_key, copy.deepcopy(r))

        with patch.object(os, "rename", side_effect=mock_rename, autospec=True):
            aliyun_oss_x.resumable_download(bucket, key, filename)

        new_r = obj.var

        self.assertTrue(new_r["tmp_suffix"] != r["tmp_suffix"])

        self.assertEqual(new_r["size"], r["size"])
        self.assertEqual(new_r["mtime"], r["mtime"])
        self.assertEqual(new_r["etag"], r["etag"])
        self.assertEqual(new_r["part_size"], r["part_size"])

        self.assertEqual(os.path.exists(filename + r["tmp_suffix"]), old_tmp_exists)
        self.assertTrue(not os.path.exists(filename + new_r["tmp_suffix"]))

        aliyun_oss_x.utils.silently_remove(filename + r["tmp_suffix"])

    def test_insane_record_modify(self):
        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 128
        aliyun_oss_x.defaults.multiget_num_threads = 3
        aliyun_oss_x.defaults.min_part_size = 128

        self.__test_insane_record(400, partial(modify_one, key="size", value="123"))
        self.__test_insane_record(400, partial(modify_one, key="mtime", value="123"))
        self.__test_insane_record(400, partial(modify_one, key="etag", value=123))

        self.__test_insane_record(400, partial(modify_one, key="part_size", value={}))
        self.__test_insane_record(400, partial(modify_one, key="tmp_suffix", value={1: 2}))
        self.__test_insane_record(400, partial(modify_one, key="parts", value={1: 2}))

        self.__test_insane_record(400, partial(modify_one, key="file_path", value=123))
        self.__test_insane_record(400, partial(modify_one, key="bucket", value=123))
        self.__test_insane_record(400, partial(modify_one, key="key", value=1.2))

    def test_insane_record_missing(self):
        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 128
        aliyun_oss_x.defaults.multiget_num_threads = 3
        aliyun_oss_x.defaults.min_part_size = 128

        def missing_one(store, store_key, r, key=None):
            del r[key]
            store.put(store_key, r)

        self.__test_insane_record(400, partial(missing_one, key="key"))
        self.__test_insane_record(400, partial(missing_one, key="mtime"))
        self.__test_insane_record(400, partial(missing_one, key="parts"))

    def test_insane_record_deleted(self):
        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 128
        aliyun_oss_x.defaults.multiget_num_threads = 3
        aliyun_oss_x.defaults.min_part_size = 128

        def delete_record(store, store_key, r):
            store.delete(store_key)

        self.__test_insane_record(400, delete_record)

    def test_insane_record_not_json(self):
        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 128
        aliyun_oss_x.defaults.multiget_num_threads = 3
        aliyun_oss_x.defaults.min_part_size = 128

        def corrupt_record(store, store_key, r):
            pathname = store._ResumableStoreBase__path(store_key)
            with open(pathname, "w") as f:
                f.write("hello}")

        self.__test_insane_record(400, corrupt_record)

    def test_remote_changed_before_start(self):
        # """在开始下载之前，OSS上的文件就已经被修改了"""
        aliyun_oss_x.defaults.multiget_threshold = 1

        # reuse __test_insane_record to simulate
        self.__test_insane_record(
            400, partial(modify_one, key="etag", value="BABEF00D123456789"), old_tmp_exists=False
        )
        self.__test_insane_record(400, partial(modify_one, key="size", value=1024), old_tmp_exists=False)
        self.__test_insane_record(400, partial(modify_one, key="mtime", value=1024), old_tmp_exists=False)

    # 测试在下载的过程中文件被修改的情况
    def test_remote_changed_during_download(self):
        bucket = random.choice([self.bucket, self.rsa_crypto_bucket, self.kms_crypto_bucket])

        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 100
        aliyun_oss_x.defaults.multiget_num_threads = 2
        aliyun_oss_x.defaults.min_part_size = 100

        orig_download_part = aliyun_oss_x.resumable._ResumableDownloader._ResumableDownloader__download_part
        orig_rename = os.rename

        file_size = 1000
        key, filename, content = self.__prepare(bucket, file_size)

        old_context = {}
        new_context = {}

        # 模拟download某个part的过程中原始文件的内容被修改了
        def mock_download_part(downloader, part, part_number=None):
            if part.part_number == part_number:
                r = self.__record(key, filename)

                old_context["tmp_suffix"] = r["tmp_suffix"]
                old_context["etag"] = r["etag"]
                old_context["content"] = random_bytes(file_size)

                bucket.put_object(key, old_context["content"])

                orig_download_part(downloader, part)

        # rename之前将新的record获取到
        def mock_rename(src, dst):
            r = self.__record(key, filename)

            new_context["tmp_suffix"] = r["tmp_suffix"]
            new_context["etag"] = r["etag"]

            orig_rename(src, dst)

        with patch.object(
            aliyun_oss_x.resumable._ResumableDownloader,
            "_ResumableDownloader__download_part",
            side_effect=partial(mock_download_part, part_number=5),
            autospec=True,
        ):
            self.assertRaises(
                aliyun_oss_x.exceptions.PreconditionFailed, aliyun_oss_x.resumable_download, bucket, key, filename
            )

        with patch.object(os, "rename", side_effect=mock_rename):
            aliyun_oss_x.resumable_download(bucket, key, filename)

        self.assertTrue(new_context["tmp_suffix"] != old_context["tmp_suffix"])
        self.assertTrue(new_context["etag"] != old_context["etag"])

    # 两个downloader同时跑，但是store的目录不一样
    def test_two_downloaders(self):
        bucket = random.choice([self.bucket, self.rsa_crypto_bucket, self.kms_crypto_bucket])
        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 100
        aliyun_oss_x.defaults.multiget_num_threads = 2
        aliyun_oss_x.defaults.min_part_size = 100

        store1 = aliyun_oss_x.make_download_store()
        store2 = aliyun_oss_x.make_download_store(dir=".another-py-oss-download")

        file_size = 1000
        key, filename, content = self.__prepare(bucket, file_size)

        context1 = {}
        context2 = {}

        def mock_rename(src, dst, ctx=None, store=None):
            r = self.__record(key, filename, store=store)

            ctx["tmp_suffix"] = r["tmp_suffix"]
            ctx["etag"] = r["etag"]
            ctx["mtime"] = r["mtime"]

            raise RuntimeError("intentional")

        with patch.object(os, "rename", side_effect=partial(mock_rename, ctx=context1, store=store1)):
            self.assertRaises(RuntimeError, aliyun_oss_x.resumable_download, bucket, key, filename, store=store1)

        with patch.object(os, "rename", side_effect=partial(mock_rename, ctx=context2, store=store2)):
            self.assertRaises(RuntimeError, aliyun_oss_x.resumable_download, bucket, key, filename, store=store2)

        self.assertNotEqual(context1["tmp_suffix"], context2["tmp_suffix"])
        self.assertEqual(context1["etag"], context2["etag"])
        self.assertEqual(context1["mtime"], context2["mtime"])

        self.assertTrue(os.path.exists(filename + context1["tmp_suffix"]))
        self.assertTrue(os.path.exists(filename + context2["tmp_suffix"]))

        aliyun_oss_x.resumable_download(bucket, key, filename, store=store1)
        self.assertTrue(not os.path.exists(filename + context1["tmp_suffix"]))

        aliyun_oss_x.resumable_download(bucket, key, filename, store=store2)
        self.assertTrue(not os.path.exists(filename + context2["tmp_suffix"]))

    def test_progress(self):
        bucket = random.choice([self.bucket, self.rsa_crypto_bucket, self.kms_crypto_bucket])
        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 100
        aliyun_oss_x.defaults.multiget_num_threads = 1
        aliyun_oss_x.defaults.min_part_size = 100

        stats = {"previous": -1, "called": 0}

        def progress_callback(bytes_consumed, total_bytes):
            self.assertTrue(bytes_consumed <= total_bytes)
            self.assertTrue(bytes_consumed > stats["previous"])

            stats["previous"] = bytes_consumed
            stats["called"] += 1

        file_size = 100 * 5 + 1
        key, filename, content = self.__prepare(bucket, file_size)

        aliyun_oss_x.resumable_download(bucket, key, filename, progress_callback=progress_callback)

        self.assertEqual(stats["previous"], file_size)
        self.assertEqual(
            stats["called"], aliyun_oss_x.utils.how_many(file_size, aliyun_oss_x.defaults.multiget_part_size) + 1
        )

    def test_parameters(self):
        bucket = random.choice([self.bucket, self.rsa_crypto_bucket, self.kms_crypto_bucket])
        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 100
        aliyun_oss_x.defaults.multiget_num_threads = 5
        aliyun_oss_x.defaults.min_part_size = 100

        context = {}

        def mock_download(downloader, server_crc=None, request_id=None):
            context["part_size"] = downloader._ResumableDownloader__part_size
            context["num_threads"] = downloader._ResumableDownloader__num_threads

            raise RuntimeError()

        file_size = 123 * 3 + 1
        key, filename, content = self.__prepare(bucket, file_size)

        with patch.object(
            aliyun_oss_x.resumable._ResumableDownloader, "download", side_effect=mock_download, autospec=True
        ):
            self.assertRaises(
                RuntimeError, aliyun_oss_x.resumable_download, bucket, key, filename, part_size=123, num_threads=3
            )

        self.assertEqual(context["part_size"], 123)
        self.assertEqual(context["num_threads"], 3)

    def test_relpath_and_abspath(self):
        # """测试绝对、相对路径"""
        # testing steps:
        #    1. first use abspath, and fail one part
        #    2. then use relpath to continue

        bucket = random.choice([self.bucket, self.rsa_crypto_bucket, self.kms_crypto_bucket])
        cwd = os.getcwd()
        if os.name == "nt":
            os.chdir("C:\\")

        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 100
        aliyun_oss_x.defaults.multiget_num_threads = 5
        aliyun_oss_x.defaults.min_part_size = 100

        fd, abspath = tempfile.mkstemp()
        os.close(fd)

        relpath = os.path.relpath(abspath)

        self.assertNotEqual(abspath, relpath)

        file_size = 1000
        key = self.random_key()
        content = random_bytes(file_size)

        bucket.put_object(key, content)

        orig_download_part = aliyun_oss_x.resumable._ResumableDownloader._ResumableDownloader__download_part
        orig_rename = os.rename

        context1 = {}
        context2 = {}

        def mock_download_part(downloader, part, part_number=None):
            if part.part_number == part_number:
                r = self.__record(key, abspath)

                context1["file_path"] = r["file_path"]
                context1["tmp_suffix"] = r["tmp_suffix"]

                raise RuntimeError("Fail download_part for part: {0}".format(part_number))
            else:
                orig_download_part(downloader, part)

        def mock_rename(src, dst):
            r = self.__record(key, relpath)

            context2["file_path"] = r["file_path"]
            context2["tmp_suffix"] = r["tmp_suffix"]

            orig_rename(src, dst)

        with patch.object(
            aliyun_oss_x.resumable._ResumableDownloader,
            "_ResumableDownloader__download_part",
            side_effect=partial(mock_download_part, part_number=3),
            autospec=True,
        ):
            self.assertRaises(RuntimeError, aliyun_oss_x.resumable_download, bucket, key, abspath)

        with patch.object(os, "rename", side_effect=mock_rename):
            aliyun_oss_x.resumable_download(bucket, key, relpath)

        self.assertEqual(context1["file_path"], context2["file_path"])
        self.assertEqual(context1["tmp_suffix"], context2["tmp_suffix"])

        aliyun_oss_x.utils.silently_remove(abspath)

        if os.name == "nt":
            os.chdir(cwd)

    def test_tmp_file_removed(self):
        bucket = random.choice([self.bucket, self.rsa_crypto_bucket, self.kms_crypto_bucket])
        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 100
        aliyun_oss_x.defaults.multiget_num_threads = 5
        aliyun_oss_x.defaults.min_part_size = 100

        orig_download_part = aliyun_oss_x.resumable._ResumableDownloader._ResumableDownloader__download_part

        file_size = 123 * 3 + 1
        key, filename, content = self.__prepare(bucket, file_size)

        context = {}

        def mock_download_part(downloader, part, part_number=None):
            if part.part_number == part_number:
                r = self.__record(key, filename)
                context["tmpfile"] = filename + r["tmp_suffix"]

                raise RuntimeError("Fail download_part for part: {0}".format(part_number))
            else:
                orig_download_part(downloader, part)

        with patch.object(
            aliyun_oss_x.resumable._ResumableDownloader,
            "_ResumableDownloader__download_part",
            side_effect=partial(mock_download_part, part_number=2),
            autospec=True,
        ):
            self.assertRaises(RuntimeError, aliyun_oss_x.resumable_download, bucket, key, filename)

        os.remove(context["tmpfile"])

        aliyun_oss_x.resumable_download(bucket, key, filename)
        self.assertFileContent(filename, content)

    def test_get_object_to_file_incomplete_download(self):
        file_size = 123 * 3 + 1
        key, filename, content = self.__prepare(self.bucket, file_size)

        with patch.object(
            aliyun_oss_x.Bucket,
            "get_object",
            side_effect=partial(mock_get_object, content_length=file_size),
            autospec=True,
        ):
            try:
                self.bucket.get_object_to_file(key, filename)
            except aliyun_oss_x.exceptions.InconsistentError as e:
                self.assertTrue(e.request_id)
                self.assertEqual(e.body, "InconsistentError: IncompleteRead from source")
            except:
                self.assertTrue(False)

    def test_get_object_to_file_incomplete_download_gzip(self):
        file_size = 1024 * 1024
        key, filename, content = self.__prepare(self.bucket, file_size, ".txt")

        with patch.object(
            aliyun_oss_x.Bucket, "get_object", side_effect=partial(mock_get_object, content_length=None), autospec=True
        ):
            self.bucket.get_object_to_file(key, filename, headers={"Accept-Encoding": "gzip"})
            self.assertFileContentNotEqual(filename, content)

    def test_resumable_incomplete_download(self):
        # """One of the part is incomplete, while there's no exception raised."""

        aliyun_oss_x.defaults.multiget_threshold = 1
        aliyun_oss_x.defaults.multiget_part_size = 100
        aliyun_oss_x.defaults.multiget_num_threads = 5
        aliyun_oss_x.defaults.min_part_size = 100

        file_size = 123 * 3 + 1
        key, filename, content = self.__prepare(self.bucket, file_size)

        with patch.object(
            aliyun_oss_x.Bucket,
            "get_object",
            side_effect=partial(mock_get_object, content_length=file_size),
            autospec=True,
        ):
            try:
                aliyun_oss_x.resumable_download(self.bucket, key, filename)
            except aliyun_oss_x.exceptions.InconsistentError as e:
                self.assertTrue(e.request_id)
                self.assertEqual(e.body, "InconsistentError: IncompleteRead from source")
            except Exception:
                self.assertTrue(False)


if __name__ == "__main__":
    unittest.main()
