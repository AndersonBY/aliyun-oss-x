import os
import asyncio

import aliyun_oss_x


access_key_id = os.getenv("OSS_TEST_ACCESS_KEY_ID", "<你的AccessKeyId>")
access_key_secret = os.getenv("OSS_TEST_ACCESS_KEY_SECRET", "<你的AccessKeySecret>")
bucket_name = os.getenv("OSS_TEST_BUCKET", "<你的Bucket>")
endpoint = os.getenv("OSS_TEST_ENDPOINT", "<你的访问域名>")
region = os.getenv("OSS_TEST_REGION", "cn-hangzhou")

auth = aliyun_oss_x.Auth(access_key_id, access_key_secret)
bucket = aliyun_oss_x.AsyncBucket(auth, endpoint, bucket_name, region=region)
service = aliyun_oss_x.AsyncService(auth, endpoint, region=region)


async def main():
    # The object key in the bucket is story.txt
    key = "story.txt"
    # Upload
    await bucket.put_object(key, "Ali Baba is a happy youth.")
    # Download
    bucket_object = await bucket.get_object(key)
    print(bucket_object.read())

    # Traverse all objects in the bucket
    async for object_info in aliyun_oss_x.AsyncObjectIterator(bucket):
        print(object_info.key, type(object_info.key))

    await bucket.delete_object(key)

    async for bucket_info in aliyun_oss_x.AsyncBucketIterator(service):
        print(bucket_info.name, type(bucket_info))


asyncio.run(main())
