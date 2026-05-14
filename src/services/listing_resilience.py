from __future__ import annotations

from collections.abc import Callable, Iterable
import logging
from typing import TypeVar

T = TypeVar("T")


def load_available_items(
    item_ids: Iterable[str],
    loader: Callable[[str], T],
    *,
    item_kind: str,
    logger: logging.Logger,
) -> list[T]:
    items: list[T] = []
    for item_id in item_ids:
        try:
            items.append(loader(item_id))
        except (FileNotFoundError, ValueError) as exc:
            logger.warning("Skipping unreadable %s during listing: %s (%s)", item_kind, item_id, exc)
    return items
