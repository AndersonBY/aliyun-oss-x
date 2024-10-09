# Alibaba Cloud OSS SDK for Python with async support

[README of Chinese](https://github.com/aliyun/aliyun-oss-python-sdk/blob/master/README-CN.rst)

## Overview

Alibaba Cloud Object Storage Python SDK with async support based on httpx and with type hints.

> [!Note]
> - This version does not contain the `osscmd` command line tool. 
> - This version only supports Python 3.10 and above.
> - This version only supports V4 Signature.

## Running environment

Python 3.10 and above.

## Installing

Install the official release version through PIP (taking Linux as an example): 

```bash
pip install aliyun-oss-x
```

## Getting started

### Sync usage

```python
import aliyun_oss_x

endpoint = 'http://oss-cn-hangzhou.aliyuncs.com' # Suppose that your bucket is in the Hangzhou region. 

auth = aliyun_oss_x.Auth('<Your AccessKeyID>', '<Your AccessKeySecret>')
bucket = aliyun_oss_x.Bucket(auth, endpoint, '<your bucket name>')

# The object key in the bucket is story.txt
key = 'story.txt'

# Upload
bucket.put_object(key, 'Ali Baba is a happy youth.')

# Download
bucket.get_object(key).read()

# Delete
bucket.delete_object(key)

# Traverse all objects in the bucket
for object_info in aliyun_oss_x.ObjectIterator(bucket):
    print(object_info.key)
```

### Async usage

```python
import asyncio

import aliyun_oss_x

endpoint = 'http://oss-cn-hangzhou.aliyuncs.com' # Suppose that your bucket is in the Hangzhou region. 

auth = aliyun_oss_x.Auth('<Your AccessKeyID>', '<Your AccessKeySecret>')
bucket = aliyun_oss_x.AsyncBucket(auth, endpoint, '<your bucket name>', region="cn-hangzhou")

async def main():
    # The object key in the bucket is story.txt
    key = 'story.txt'

    # Upload
    await bucket.put_object(key, 'Ali Baba is a happy youth.')

    # Download
    await bucket.get_object(key).read()

    # Delete
    await bucket.delete_object(key)

    # Traverse all objects in the bucket
    async for object_info in aliyun_oss_x.AsyncObjectIterator(bucket):
        print(object_info.key)

asyncio.run(main())
```

For more examples, refer to the code under the "examples" directory. 

## Handling errors

The Python SDK interface will throw an exception in case of an error (see aliyun_oss_x.exceptions sub-module) unless otherwise specified. An example is provided below:

```python
try:
    result = bucket.get_object(key)
    print(result.read())
except aliyun_oss_x.exceptions.NoSuchKey as e:
    print('{0} not found: http_status={1}, request_id={2}'.format(key, e.status, e.request_id))
```

## Setup Logging

The following code can set the logging level of 'aliyun_oss_x'.

```python
import logging
logging.getLogger('aliyun_oss_x').setLevel(logging.WARNING)
```

## Testing

First set the required AccessKeyId, AccessKeySecret, endpoint and bucket information for the test through environment variables (**Do not use the bucket for the production environment**). 
Take the Linux system for example: 

```bash
export OSS_TEST_ACCESS_KEY_ID=<AccessKeyId>
export OSS_TEST_ACCESS_KEY_SECRET=<AccessKeySecret>
export OSS_TEST_ENDPOINT=<endpoint>
export OSS_TEST_BUCKET=<bucket>

export OSS_TEST_STS_ID=<AccessKeyId for testing STS>
export OSS_TEST_STS_KEY=<AccessKeySecret for testing STS>
export OSS_TEST_STS_ARN=<Role ARN for testing STS>
```

Run the test in the following method: 

```bash
nosetests                          # First install nose
```

## More resources
- [More examples](https://github.com/aliyun/aliyun-oss-python-sdk/tree/master/examples). 
- [Python SDK API documentation](http://aliyun-oss-python-sdk.readthedocs.org/en/latest). 
- [Official Python SDK documentation](https://help.aliyun.com/document_detail/32026.html).

## Contacting us
- [Alibaba Cloud OSS official website](http://oss.aliyun.com).
- [Alibaba Cloud OSS official forum](http://bbs.aliyun.com).
- [Alibaba Cloud OSS official documentation center](https://help.aliyun.com/document_detail/32026.html).
- Alibaba Cloud official technical support: [Submit a ticket](https://workorder.console.aliyun.com/#/ticket/createIndex).

## License
- [MIT](https://github.com/aliyun/aliyun-oss-python-sdk/blob/master/LICENSE).