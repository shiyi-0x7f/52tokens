"""采集器注册表：kind → Collector 子类。"""

from typing import Any

from app.collectors.base import Collector

_REGISTRY: dict[str, type[Collector[Any]]] = {}


def register[C: type[Collector[Any]]](cls: C) -> C:
    kind = cls.kind
    if kind in _REGISTRY and _REGISTRY[kind] is not cls:
        raise ValueError(f"采集器 kind 重复注册：{kind}")
    _REGISTRY[kind] = cls
    return cls


def get_collector_class(kind: str) -> type[Collector[Any]]:
    try:
        return _REGISTRY[kind]
    except KeyError:
        raise ValueError(f"未知的采集器 kind：{kind}") from None


def registered_kinds() -> list[str]:
    return sorted(_REGISTRY)
