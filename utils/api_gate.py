import threading
from contextlib import contextmanager

from utils.limits import max_api_concurrency

_semaphore: threading.Semaphore | None = None
_init_lock = threading.Lock()


def _get_semaphore() -> threading.Semaphore:
    global _semaphore
    if _semaphore is None:
        with _init_lock:
            if _semaphore is None:
                _semaphore = threading.Semaphore(max_api_concurrency())
    return _semaphore


@contextmanager
def api_slot():
    """Limit concurrent outbound LLM HTTP calls across all parallel workers."""
    _get_semaphore().acquire()
    try:
        yield
    finally:
        _get_semaphore().release()
