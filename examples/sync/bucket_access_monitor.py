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

# Configure access monitor for the bucket.
# If status is set to Enabled, access monitor is enabled. If status is set to Disabled, access monitor is disabled.
status = "Enabled"
bucket.put_bucket_access_monitor(status)

# Query the access monitor status of the bucket.
result = bucket.get_bucket_access_monitor()
status = result.access_monitor.status
print("Return access monitor status: ", status)
