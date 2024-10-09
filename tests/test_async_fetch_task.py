import time
import unittest

import aliyun_oss_x
from aliyun_oss_x.compat import to_bytes
from aliyun_oss_x.models import (
    AsyncFetchTaskConfiguration,
    ASYNC_FETCH_TASK_STATE_SUCCESS,
    ASYNC_FETCH_TASK_STATE_FETCH_SUCCESS_CALLBACK_FAILED,
    ASYNC_FETCH_TASK_STATE_FAILED,
)
from .common import (
    OSS_ID,
    OSS_SECRET,
    OSS_BUCKET_BASE,
    OssTestCase,
    random_string,
)


class TestAsyncFetchTask(OssTestCase):
    def setUp(self):
        self.endpoint = "oss-cn-hangzhou.aliyuncs.com"
        self.OSS_BUCKET = OSS_BUCKET_BASE + random_string(4)
        self.bucket = aliyun_oss_x.Bucket(aliyun_oss_x.make_auth(OSS_ID, OSS_SECRET), self.endpoint, self.OSS_BUCKET)
        self.bucket.create_bucket()

        self.fetch_object_name = "test-async-fetch-task.txt"
        self.bucket.put_object(self.fetch_object_name, "123")

        meta = self.bucket.head_object(self.fetch_object_name)
        self.fetch_content_md5 = meta.headers.get("Content-MD5")
        self.fetch_url = self.bucket.sign_url("GET", self.fetch_object_name, 60 * 60)

        self.key_list = []
        self.temp_files = []

    def test_async_fetch_task(self):
        auth = aliyun_oss_x.Auth(OSS_ID, OSS_SECRET)
        bucket_name = self.OSS_BUCKET + "-test-async-fetch-task"
        bucket = aliyun_oss_x.Bucket(auth, self.endpoint, bucket_name)
        bucket.create_bucket()

        object_name = self.fetch_object_name + "-destination"
        task_config = AsyncFetchTaskConfiguration(
            self.fetch_url, object_name=object_name, content_md5=self.fetch_content_md5, ignore_same_key=False
        )

        result = bucket.put_async_fetch_task(task_config)
        task_id = result.task_id
        time.sleep(5)

        result = bucket.get_async_fetch_task(task_id)
        self.assertEqual(task_id, result.task_id)
        self.assertEqual(ASYNC_FETCH_TASK_STATE_SUCCESS, result.task_state)
        self.assertEqual("", result.error_msg)
        task_config = result.task_config
        if task_config is None:
            raise Exception("task_config is None")
        self.assertEqual(self.fetch_url, task_config.url)
        self.assertEqual(self.fetch_content_md5, task_config.content_md5)
        self.assertEqual(object_name, task_config.object_name)
        self.assertFalse(task_config.ignore_same_key)
        self.assertEqual("", task_config.host)
        self.assertEqual("", task_config.callback)

        bucket.delete_object(object_name)
        bucket.delete_bucket()

    def test_async_fetch_task_with_few_argument(self):
        auth = aliyun_oss_x.Auth(OSS_ID, OSS_SECRET)
        bucket_name = self.OSS_BUCKET + "-test-async-fetch-task"
        bucket = aliyun_oss_x.Bucket(auth, self.endpoint, bucket_name)
        bucket.create_bucket()

        object_name = self.fetch_object_name + "-destination"
        task_config = AsyncFetchTaskConfiguration(self.fetch_url, object_name)

        result = bucket.put_async_fetch_task(task_config)
        task_id = result.task_id
        time.sleep(5)

        result = bucket.get_async_fetch_task(task_id)
        self.assertEqual(task_id, result.task_id)
        self.assertEqual(ASYNC_FETCH_TASK_STATE_SUCCESS, result.task_state)
        self.assertEqual("", result.error_msg)
        task_config = result.task_config
        if task_config is None:
            raise Exception("task_config is None")
        self.assertEqual(self.fetch_url, task_config.url)
        self.assertEqual("", task_config.content_md5)
        self.assertEqual(object_name, task_config.object_name)
        self.assertTrue(task_config.ignore_same_key)
        self.assertEqual("", task_config.host)
        self.assertEqual("", task_config.callback)

        bucket.delete_object(object_name)
        bucket.delete_bucket()

    def test_fetch_success_callback_failed_state(self):
        auth = aliyun_oss_x.Auth(OSS_ID, OSS_SECRET)
        bucket_name = self.OSS_BUCKET + "-test-async-fetch-task-callback"
        bucket = aliyun_oss_x.Bucket(auth, self.endpoint, bucket_name)
        bucket.create_bucket()

        object_name = self.fetch_object_name + "-destination"
        callback = '{"callbackUrl":"www.abc.com/callback","callbackBody":"${etag}"}'
        base64_callback = aliyun_oss_x.utils.b64encode_as_string(to_bytes(callback))
        task_config = AsyncFetchTaskConfiguration(self.fetch_url, object_name=object_name, callback=base64_callback)

        result = bucket.put_async_fetch_task(task_config)
        task_id = result.task_id
        time.sleep(5)

        result = bucket.get_async_fetch_task(task_id)

        self.assertEqual(task_id, result.task_id)
        self.assertEqual(ASYNC_FETCH_TASK_STATE_FETCH_SUCCESS_CALLBACK_FAILED, result.task_state)
        self.assertNotEqual("", result.error_msg)
        task_config = result.task_config
        if task_config is None:
            raise Exception("task_config is None")
        self.assertEqual(self.fetch_url, task_config.url)
        self.assertEqual("", task_config.content_md5)
        self.assertEqual(object_name, task_config.object_name)
        self.assertTrue(task_config.ignore_same_key)
        self.assertEqual("", task_config.host)
        self.assertEqual(base64_callback, task_config.callback)

        bucket.delete_object(object_name)
        bucket.delete_bucket()

    def test_failed_state(self):
        auth = aliyun_oss_x.Auth(OSS_ID, OSS_SECRET)
        bucket_name = self.OSS_BUCKET + "-test-async-fetch-task-callback"
        bucket = aliyun_oss_x.Bucket(auth, self.endpoint, bucket_name)
        bucket.create_bucket()

        object_name = self.fetch_object_name + "-destination"

        task_config = AsyncFetchTaskConfiguration("http://invalidUrl.com", object_name=object_name)

        result = bucket.put_async_fetch_task(task_config)
        task_id = result.task_id
        time.sleep(5)

        result = bucket.get_async_fetch_task(task_id)

        self.assertEqual(task_id, result.task_id)
        self.assertEqual(ASYNC_FETCH_TASK_STATE_FAILED, result.task_state)
        self.assertNotEqual("", result.error_msg)

        bucket.delete_bucket()

    def test_ignore_same_key(self):
        auth = aliyun_oss_x.Auth(OSS_ID, OSS_SECRET)
        bucket_name = self.OSS_BUCKET + "-test-async-fetch-task"
        bucket = aliyun_oss_x.Bucket(auth, self.endpoint, bucket_name)
        bucket.create_bucket()

        object_name = self.fetch_object_name + "-destination"
        bucket.put_object(object_name, "test-content")

        task_config = AsyncFetchTaskConfiguration(self.fetch_url, object_name=object_name, ignore_same_key=False)
        result = bucket.put_async_fetch_task(task_config)
        task_id = result.task_id
        self.assertNotEqual("", task_id)

        task_config = AsyncFetchTaskConfiguration(self.fetch_url, object_name=object_name, ignore_same_key=True)
        self.assertRaises(aliyun_oss_x.exceptions.ObjectAlreadyExists, bucket.put_async_fetch_task, task_config)

        task_config = AsyncFetchTaskConfiguration(self.fetch_url, object_name=object_name)
        self.assertRaises(aliyun_oss_x.exceptions.ObjectAlreadyExists, bucket.put_async_fetch_task, task_config)

        bucket.delete_object(object_name)

    def test_fetch_success_callback_failed(self):
        auth = aliyun_oss_x.Auth(OSS_ID, OSS_SECRET)
        bucket_name = self.OSS_BUCKET + "-test-async-fetch-callback-failed"
        bucket = aliyun_oss_x.Bucket(auth, self.endpoint, bucket_name)
        bucket.create_bucket()

        object_name = self.fetch_object_name + "-destination"
        callback = '{"callbackUrl":"www.abc.com/callback","callbackBody":"${etag}"}'
        base64_callback = aliyun_oss_x.utils.b64encode_as_string(to_bytes(callback))
        task_config = AsyncFetchTaskConfiguration(
            self.fetch_url, object_name=object_name, callback=base64_callback, callback_when_failed=False
        )

        result = bucket.put_async_fetch_task(task_config)
        task_id = result.task_id
        time.sleep(5)

        result = bucket.get_async_fetch_task(task_id)

        self.assertEqual(task_id, result.task_id)
        self.assertEqual(ASYNC_FETCH_TASK_STATE_FETCH_SUCCESS_CALLBACK_FAILED, result.task_state)
        self.assertNotEqual("", result.error_msg)
        task_config = result.task_config
        if task_config is None:
            raise Exception("task_config is None")
        self.assertEqual(self.fetch_url, task_config.url)
        self.assertEqual("", task_config.content_md5)
        self.assertEqual(object_name, task_config.object_name)
        self.assertTrue(task_config.ignore_same_key)
        self.assertEqual("", task_config.host)
        self.assertEqual(base64_callback, task_config.callback)

        bucket.delete_object(object_name)
        bucket.delete_bucket()


if __name__ == "__main__":
    unittest.main()
