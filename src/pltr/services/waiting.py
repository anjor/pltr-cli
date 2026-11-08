"""Polling until asynchronous work finishes (``--wait``, #195)."""

import time
from typing import Callable, Optional, TypeVar

T = TypeVar("T")

#: Seconds between the first polls; each wait grows by BACKOFF up to MAX_POLL.
FIRST_POLL = 2.0
BACKOFF = 1.5
MAX_POLL = 30.0


def wait_until(
    fetch: Callable[[], T],
    done: Callable[[T], bool],
    *,
    timeout: float,
    on_timeout: Callable[[T], Exception],
    current: Optional[T] = None,
) -> T:
    """Call ``fetch`` with backoff until ``done(value)``; return that value.

    ``current`` is the latest value if already known (saves one call). After
    ``timeout`` seconds raises ``on_timeout(latest value)``.
    """
    deadline = time.monotonic() + timeout
    value = fetch() if current is None else current
    interval = FIRST_POLL
    while not done(value):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise on_timeout(value)
        time.sleep(min(interval, remaining))
        interval = min(interval * BACKOFF, MAX_POLL)
        value = fetch()
    return value
