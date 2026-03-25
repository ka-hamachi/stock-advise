from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

from src.storage.models import RawItem


class BaseCollector(ABC):
    @abstractmethod
    def collect(self) -> list[RawItem]:
        ...

    @staticmethod
    def make_hash(source: str, url: str | None, title: str) -> str:
        key = f"{source}:{url or ''}:{title}"
        return hashlib.sha256(key.encode()).hexdigest()
