import aliyun_oss_x
from aliyun_oss_x.credentials import EnvironmentVariableCredentialsProvider

# Specify access information, such as Endpoint, BucketName.
# You can obtain access information from evironment variables , such as <OSS_ACCESS_KEY_ID>, <OSS_ACCESS_KEY_SECRET> and <OSS_SESSION_TOKEN>.
# Please set the above environment variables on the server before execution
#
# For example, if your bucket is located in the China (Hangzhou) region, you can set Endpoint to one of the following values:
#   http://oss-cn-hangzhou.aliyuncs.com
#   https://oss-cn-hangzhou.aliyuncs.com

credentials_provider = EnvironmentVariableCredentialsProvider()
auth = aliyun_oss_x.ProviderAuth(credentials_provider)
bucket = aliyun_oss_x.Bucket(auth, "<yourEndpoint>", "<yourBucketName>")

result = bucket.put_object("sample.txt", "hello world")

print("Returns status code: ", result.status)
