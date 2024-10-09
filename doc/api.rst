.. _api:

API文档
==========

.. module:: aliyun_oss_x

基础类
------

.. autoclass:: aliyun_oss_x.Auth
.. autoclass:: aliyun_oss_x.AnonymousAuth
.. autoclass:: aliyun_oss_x.StsAuth
.. autoclass:: aliyun_oss_x.Bucket
.. autoclass:: aliyun_oss_x.Service
.. autoclass:: aliyun_oss_x.Session

输入、输出和异常说明
------------------

.. automodule:: aliyun_oss_x.api

文件（Object）相关操作
--------------------

上传
~~~~
.. automethod:: aliyun_oss_x.Bucket.put_object
.. automethod:: aliyun_oss_x.Bucket.put_object_from_file
.. automethod:: aliyun_oss_x.Bucket.append_object


下载
~~~~
.. automethod:: aliyun_oss_x.Bucket.get_object
.. automethod:: aliyun_oss_x.Bucket.get_object_to_file


删除
~~~~
.. automethod:: aliyun_oss_x.Bucket.delete_object
.. automethod:: aliyun_oss_x.Bucket.batch_delete_objects


罗列
~~~~
.. automethod:: aliyun_oss_x.Bucket.list_objects

获取、更改文件信息
~~~~~~~~~~~~~~~

.. automethod:: aliyun_oss_x.Bucket.head_object
.. automethod:: aliyun_oss_x.Bucket.object_exists
.. automethod:: aliyun_oss_x.Bucket.put_object_acl
.. automethod:: aliyun_oss_x.Bucket.get_object_acl
.. automethod:: aliyun_oss_x.Bucket.update_object_meta
.. automethod:: aliyun_oss_x.Bucket.get_object_meta


分片上传
~~~~~~~~

.. automethod:: aliyun_oss_x.Bucket.init_multipart_upload
.. automethod:: aliyun_oss_x.Bucket.upload_part
.. automethod:: aliyun_oss_x.Bucket.complete_multipart_upload
.. automethod:: aliyun_oss_x.Bucket.abort_multipart_upload
.. automethod:: aliyun_oss_x.Bucket.list_multipart_uploads
.. automethod:: aliyun_oss_x.Bucket.list_parts


符号链接
~~~~~~~~

.. automethod:: aliyun_oss_x.Bucket.put_symlink
.. automethod:: aliyun_oss_x.Bucket.get_symlink


存储空间（Bucket）相关操作
-------------------------

创建、删除、查询
~~~~~~~~~~~~~~

.. automethod:: aliyun_oss_x.Bucket.create_bucket
.. automethod:: aliyun_oss_x.Bucket.delete_bucket
.. automethod:: aliyun_oss_x.Bucket.get_bucket_location

Bucket权限管理
~~~~~~~~~~~~~~
.. automethod:: aliyun_oss_x.Bucket.put_bucket_acl
.. automethod:: aliyun_oss_x.Bucket.get_bucket_acl


跨域资源共享（CORS）
~~~~~~~~~~~~~~~~~~~~
.. automethod:: aliyun_oss_x.Bucket.put_bucket_cors
.. automethod:: aliyun_oss_x.Bucket.get_bucket_cors
.. automethod:: aliyun_oss_x.Bucket.delete_bucket_cors


生命周期管理
~~~~~~~~~~~
.. automethod:: aliyun_oss_x.Bucket.put_bucket_lifecycle
.. automethod:: aliyun_oss_x.Bucket.get_bucket_lifecycle
.. automethod:: aliyun_oss_x.Bucket.delete_bucket_lifecycle


日志收集
~~~~~~~~

.. automethod:: aliyun_oss_x.Bucket.put_bucket_logging
.. automethod:: aliyun_oss_x.Bucket.get_bucket_logging
.. automethod:: aliyun_oss_x.Bucket.delete_bucket_logging

防盗链
~~~~~~

.. automethod:: aliyun_oss_x.Bucket.put_bucket_referer
.. automethod:: aliyun_oss_x.Bucket.get_bucket_referer

静态网站托管
~~~~~~~~~~~~

.. automethod:: aliyun_oss_x.Bucket.put_bucket_website
.. automethod:: aliyun_oss_x.Bucket.get_bucket_website
.. automethod:: aliyun_oss_x.Bucket.delete_bucket_website


RTPM推流操作
~~~~~~~~~~~~

.. automethod:: aliyun_oss_x.Bucket.create_live_channel
.. automethod:: aliyun_oss_x.Bucket.delete_live_channel
.. automethod:: aliyun_oss_x.Bucket.get_live_channel
.. automethod:: aliyun_oss_x.Bucket.list_live_channel
.. automethod:: aliyun_oss_x.Bucket.get_live_channel_stat
.. automethod:: aliyun_oss_x.Bucket.put_live_channel_status
.. automethod:: aliyun_oss_x.Bucket.get_live_channel_history
.. automethod:: aliyun_oss_x.Bucket.post_vod_playlist