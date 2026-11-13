"""Cache em memória com TTL (substitui o Redis do desenho original no MVP).

Suficiente para uma instância única. Para múltiplas instâncias, troque por Redis
mantendo a mesma interface ``get_or_set`` / ``clear``.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: float = 300.0):
        self.ttl = ttl_seconds
        self._items: dict[Any, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: Any, factory: Callable[[], Any], ttl: float | None = None) -> Any:
        now = time.monotonic()
        with self._lock:
            hit = self._items.get(key)
            if hit and hit[0] > now:
                return hit[1]
        value = factory()  # fora do lock: não bloqueia outras requisições
        with self._lock:
            self._items[key] = (now + (self.ttl if ttl is None else ttl), value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
