.. _easy:


易用性接口
==========

.. module:: aliyun_oss_x

迭代器
~~~~~~

.. autoclass:: aliyun_oss_x.BucketIterator
.. autoclass:: aliyun_oss_x.ObjectIterator
.. autoclass:: aliyun_oss_x.MultipartUploadIterator
.. autoclass:: aliyun_oss_x.ObjectUploadIterator
.. autoclass:: aliyun_oss_x.PartIterator


断点续传（上传、下载）
~~~~~~~~~~~~~~~~~~~

.. autofunction:: aliyun_oss_x.resumable_upload
.. autofunction:: aliyun_oss_x.resumable_download

FileObject适配器
~~~~~~~~~~~~~~~~~~

.. autoclass:: aliyun_oss_x.SizedFileAdapter