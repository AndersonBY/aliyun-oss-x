# -*- coding: utf-8 -*-

import time
import os

import aliyun_oss_x


# 以下代码展示了Bucket相关操作，诸如创建、删除、列举Bucket等。


# 首先初始化AccessKeyId、AccessKeySecret、Endpoint等信息。
# 通过环境变量获取，或者把诸如“<你的AccessKeyId>”替换成真实的AccessKeyId等。
access_key_id = os.getenv("OSS_TEST_ACCESS_KEY_ID", "<你的AccessKeyId>")
access_key_secret = os.getenv("OSS_TEST_ACCESS_KEY_SECRET", "<你的AccessKeySecret>")
bucket_name = os.getenv("OSS_TEST_BUCKET", "<你的Bucket>")
endpoint = os.getenv("OSS_TEST_ENDPOINT", "<你的访问域名>")


# 确认上面的参数都填写正确了
for param in (access_key_id, access_key_secret, bucket_name, endpoint):
    assert "<" not in param, "请设置参数：" + param


# 列举所有的Bucket
#   1. 先创建一个Service对象
#   2. 用aliyun_oss_x.BucketIterator遍历
service = aliyun_oss_x.Service(aliyun_oss_x.Auth(access_key_id, access_key_secret), endpoint)
print("\n".join(info.name for info in aliyun_oss_x.BucketIterator(service)))

# 列举所有的Bucket,单region场景
params = {}
params["regionList"] = ""
result = service.list_buckets(params=params)
for bucket_info in result.buckets:
    print("name: " + bucket_info.name)

# 创建Bucket对象，所有Object相关的接口都可以通过Bucket对象来进行
bucket = aliyun_oss_x.Bucket(aliyun_oss_x.Auth(access_key_id, access_key_secret), endpoint, bucket_name)

# 带权限与存储类型创建bucket
bucket.create_bucket(
    permission=aliyun_oss_x.BUCKET_ACL_PRIVATE,
    input=aliyun_oss_x.models.BucketCreateConfig(aliyun_oss_x.BUCKET_STORAGE_CLASS_STANDARD),
)

# 获取bucket相关信息
bucket_info = bucket.get_bucket_info()
print("name: " + bucket_info.name)
print("storage class: " + bucket_info.storage_class)
print("creation date: " + bucket_info.creation_date)

# 查看Bucket的状态
bucket_stat = bucket.get_bucket_stat()
print("storage: " + str(bucket_stat.storage_size_in_bytes))
print("object count: " + str(bucket_stat.object_count))
print("multi part upload count: " + str(bucket_stat.multi_part_upload_count))

# 设置bucket生命周期， 有'中文/'前缀的对象在最后修改时间之后357天失效
rule = aliyun_oss_x.models.LifecycleRule(
    "lc_for_chinese_prefix",
    "中文/",
    status=aliyun_oss_x.models.LifecycleRule.ENABLED,
    expiration=aliyun_oss_x.models.LifecycleExpiration(days=357),
)

# 删除相对最后修改时间365天之后的parts
rule.abort_multipart_upload = aliyun_oss_x.models.AbortMultipartUpload(days=356)
# 对象最后修改时间超过180天后转为IA
rule.storage_transitions = [
    aliyun_oss_x.models.StorageTransition(days=180, storage_class=aliyun_oss_x.BUCKET_STORAGE_CLASS_IA)
]
# 对象最后修改时间超过356天后转为ARCHIVE
rule.storage_transitions.append(
    aliyun_oss_x.models.StorageTransition(days=356, storage_class=aliyun_oss_x.BUCKET_STORAGE_CLASS_ARCHIVE)
)

lifecycle = aliyun_oss_x.models.BucketLifecycle([rule])
bucket.put_bucket_lifecycle(lifecycle)

# 下面只展示如何配置静态网站托管。其他的Bucket操作方式类似，可以参考tests/test_bucket.py里的内容

# 方法一：可以生成一个BucketWebsite对象来设置
bucket.put_bucket_website(aliyun_oss_x.models.BucketWebsite("index.html", "error.html"))

# 方法二：可以直接设置XML
xml = """
<WebsiteConfiguration>
    <IndexDocument>
        <Suffix>index2.html</Suffix>
    </IndexDocument>

    <ErrorDocument>
        <Key>error2.html</Key>
    </ErrorDocument>
</WebsiteConfiguration>
"""
bucket.put_bucket_website(xml)

# 方法三：可以从本地文件读取XML配置
# aliyun_oss_x.to_bytes()可以把unicode转换为bytes
with open("website_config.xml", "wb") as f:
    f.write(aliyun_oss_x.to_bytes(xml))

with open("website_config.xml", "rb") as f:
    bucket.put_bucket_website(f)

os.remove("website_config.xml")


# 获取配置
# 因为是分布式系统，所以配置刚刚设置好，可能还不能立即获取到，先等几秒钟
time.sleep(5)

result = bucket.get_bucket_website()
assert result.index_file == "index2.html"
assert result.error_file == "error2.html"


# 取消静态网站托管模式
bucket.delete_bucket_website()

# Obtain the region of the bucket
result = bucket.get_bucket_location()
print("location: " + result.location)


# Determine whether a bucket exists
def does_bucket_exist(bucket):
    try:
        bucket.get_bucket_info()
    except aliyun_oss_x.exceptions.NoSuchBucket:
        return False
    except:
        raise
    return True


exist = does_bucket_exist(bucket)
# If the returned value is true, a bucket with the specified name exists. If the returned value is false, a bucket with the specified name does not exist.
if exist:
    print("bucket exist")
else:
    print("bucket not exist")


# Configure the ACL of the bucket to private
bucket.put_bucket_acl(aliyun_oss_x.BUCKET_ACL_PRIVATE)

# Obtain the ACL of a bucket
bucket.put_bucket_acl(aliyun_oss_x.BUCKET_ACL_PRIVATE)
print(bucket.get_bucket_acl().acl)
