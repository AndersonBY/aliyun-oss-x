import os
import asyncio

import aliyun_oss_x


access_key_id = os.getenv("OSS_TEST_ACCESS_KEY_ID", "<你的AccessKeyId>")
access_key_secret = os.getenv("OSS_TEST_ACCESS_KEY_SECRET", "<你的AccessKeySecret>")
bucket_name = os.getenv("OSS_TEST_BUCKET", "<你的Bucket>")
endpoint = os.getenv("OSS_TEST_ENDPOINT", "<你的访问域名>")
region = os.getenv("OSS_TEST_REGION", "cn-hangzhou")

auth = aliyun_oss_x.Auth(access_key_id, access_key_secret)
bucket = aliyun_oss_x.Bucket(auth, endpoint, bucket_name, region=region)
service = aliyun_oss_x.Service(auth, endpoint, region=region)


key = "story.txt"
content = "a" * 1024

# Upload
bucket.put_object(key, content)
# Get the object size
result = bucket.head_object(key)
print(f"Content-Length: {result.content_length}")
# Download
bucket_object = bucket.get_object(key)
# print(bucket_object.read())
print(bucket_object.content_length)

# Traverse all objects in the bucket
for object_info in aliyun_oss_x.ObjectIterator(bucket):
    print(object_info.key, type(object_info.key))

bucket.delete_object(key)

for bucket_info in aliyun_oss_x.BucketIterator(service):
    print(bucket_info.name, type(bucket_info))
