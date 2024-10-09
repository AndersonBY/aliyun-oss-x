from typing import overload, TypeVar, Union, cast


def to_bytes(data):
    """若输入为str（即unicode），则转为utf-8编码的bytes；其他则原样返回"""
    if isinstance(data, str):
        return data.encode(encoding="utf-8")
    else:
        return data


T = TypeVar("T")


@overload
def to_string(data: bytes) -> str: ...


@overload
def to_string(data: T) -> T: ...


def to_string(data: Union[bytes, T]) -> Union[str, T]:
    """若输入为bytes，则认为是utf-8编码，并返回str；否则原样返回"""
    if isinstance(data, bytes):
        return data.decode(encoding="utf-8")
    else:
        return cast(T, data)


def to_unicode(data):
    """把输入转换为unicode，要求输入是unicode或者utf-8编码的bytes。"""
    return to_string(data)


def stringify(input):
    return input
