from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar

from utils.limits import max_api_concurrency

T = TypeVar("T")
R = TypeVar("R")


def map_parallel_ordered(
    items: list[T],
    fn: Callable[[T], R],
    *,
    max_workers: int | None = None,
) -> list[R]:
    """Run fn on each item in parallel; return results in the same order as items."""
    if not items:
        return []
    if len(items) == 1:
        return [fn(items[0])]

    cap = max_workers if max_workers is not None else max_api_concurrency()
    workers = min(len(items), cap)
    results: list[R | None] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fn, item): index for index, item in enumerate(items)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return results  # type: ignore[return-value]
