"""Generic plugin registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """A named registry mapping string keys to implementations.

    Usage::

        registry: Registry[type[BaseParser]] = Registry("parser")

        @registry.register("rss")
        class RSSParser(BaseParser):
            ...

        parser_cls = registry.get("rss")
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._items: dict[str, T] = {}

    def register(self, key: str) -> Callable[[T], T]:
        """Decorator registering ``obj`` under ``key``."""

        def decorator(obj: T) -> T:
            normalized = key.lower()
            if normalized in self._items:
                raise ValueError(f"{self.name} plugin '{key}' already registered")
            self._items[normalized] = obj
            return obj

        return decorator

    def register_instance(self, key: str, obj: T) -> None:
        """Imperatively register an object."""
        self._items[key.lower()] = obj

    def get(self, key: str) -> T:
        """Return the plugin registered under ``key``.

        Raises ``KeyError`` if not found.
        """
        try:
            return self._items[key.lower()]
        except KeyError as exc:
            raise KeyError(
                f"No {self.name} plugin registered for '{key}'. "
                f"Available: {', '.join(sorted(self._items))}"
            ) from exc

    def has(self, key: str) -> bool:
        return key.lower() in self._items

    def keys(self) -> list[str]:
        return sorted(self._items)

    def all(self) -> dict[str, T]:
        return dict(self._items)
