from typing import TypeVar, Any, Protocol

from httpx._types import ProxiesTypes


class ResultProtocol(Protocol):
    def __init__(self, resp: Any) -> None: ...


ResultType = TypeVar("ResultType", bound=ResultProtocol)


__all__ = ["ResultType", "ProxiesTypes"]
