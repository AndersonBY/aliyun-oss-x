import os
import aliyun_oss_x

# Specify access information, such as AccessKeyId, AccessKeySecret, and Endpoint.
# You can obtain access information from evironment variables or replace sample values in the code, such as <your AccessKeyId> with actual values.
#
# For example, if your bucket is located in the China (Hangzhou) region, you can set Endpoint to one of the following values:
#   http://oss-cn-hangzhou.aliyuncs.com
#   https://oss-cn-hangzhou.aliyuncs.com


access_key_id = os.getenv("OSS_TEST_ACCESS_KEY_ID", "<yourAccessKeyId>")
access_key_secret = os.getenv("OSS_TEST_ACCESS_KEY_SECRET", "<yourAccessKeySecret>")
bucket_name = os.getenv("OSS_TEST_BUCKET", "<yourBucketName>")
endpoint = os.getenv("OSS_TEST_ENDPOINT", "<yourEndpoint>")


# Make sure that all parameters are correctly configured
for param in (access_key_id, access_key_secret, bucket_name, endpoint):
    assert "<" not in param, "Please set parameters：" + param


# Create a bucket. You can use the bucket to call all object-related operations
bucket = aliyun_oss_x.Bucket(aliyun_oss_x.Auth(access_key_id, access_key_secret), endpoint, bucket_name)

# Configure archive direct read for the bucket.
bucket.put_bucket_archive_direct_read(True)

# Query the archive direct read of the bucket.
result = bucket.get_bucket_archive_direct_read()
print("Return archive direct read: ", result.enabled)
