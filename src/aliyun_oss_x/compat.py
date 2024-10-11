from typing import overload, TypeVar, Union, cast

T = TypeVar("T")


@overload
def to_bytes(data: str) -> bytes: ...


@overload
def to_bytes(data: T) -> T: ...


def to_bytes(data: Union[str, T]) -> Union[bytes, T]:
    """若输入为str（即unicode），则转为utf-8编码的bytes；其他则原样返回"""
    if isinstance(data, str):
        return data.encode(encoding="utf-8")
    else:
        return data
