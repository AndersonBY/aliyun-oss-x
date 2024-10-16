import os
import aliyun_oss_x

# Specify access information, such as AccessKeyId, AccessKeySecret, and Endpoint.
# You can obtain access information from evironment variables or replace sample values in the code, such as <your AccessKeyId> with actual values.
#
# For example, if your bucket is located in the China (Hangzhou) region, you can set Endpoint to one of the following values:
#   http://oss-cn-hangzhou.aliyuncs.com
#   https://oss-cn-hangzhou.aliyuncs.com
from aliyun_oss_x.models import BucketTlsVersion

access_key_id = os.getenv("OSS_TEST_ACCESS_KEY_ID", "<yourAccessKeyId>")
access_key_secret = os.getenv("OSS_TEST_ACCESS_KEY_SECRET", "<yourAccessKeySecret>")
bucket_name = os.getenv("OSS_TEST_BUCKET", "<yourBucketName>")
endpoint = os.getenv("OSS_TEST_ENDPOINT", "<yourEndpoint>")


# Make sure that all parameters are correctly configured
for param in (access_key_id, access_key_secret, bucket_name, endpoint):
    assert "<" not in param, "Please set parameters：" + param


# Create a bucket. You can use the bucket to call all object-related operations
bucket = aliyun_oss_x.Bucket(aliyun_oss_x.Auth(access_key_id, access_key_secret), endpoint, bucket_name)

# Configure transfer acceleration for the bucket.
# If enabled is set to true, transfer acceleration is enabled. If enabled is set to false, transfer acceleration is disabled.
https_config = BucketTlsVersion(True, ["TLSv1.2", "TLSv1.3"])
bucket.put_bucket_https_config(https_config)

# Query the transfer acceleration status of the bucket.
# If the returned value is true, the transfer acceleration feature is enabled for the bucket. If the returned value is false, the transfer acceleration feature is disabled for the bucket.
result = bucket.get_bucket_https_config()
print("Return information on whether to enable TLS version settings: {0}".format(result.tls_enabled))
print("Return TLS version number: {0}".format(result.tls_version))
