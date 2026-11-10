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
    max_poll: float = MAX_POLL,
) -> T:
    """Call ``fetch`` with backoff until ``done(value)``; return that value.

    ``current`` is the latest value if already known (saves one call). After
    ``timeout`` seconds raises ``on_timeout(latest value)``. The wait between
    calls grows from FIRST_POLL by BACKOFF up to ``max_poll`` seconds.
    """
    deadline = time.monotonic() + timeout
    value = fetch() if current is None else current
    interval = FIRST_POLL
    while not done(value):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise on_timeout(value)
        time.sleep(min(interval, remaining))
        interval = min(interval * BACKOFF, max_poll)
        try:
            value = fetch()
        except Exception as exc:
            # A rate limit, 5xx or network error while polling: the work keeps
            # going, so keep polling until the deadline.
            if not is_transient(exc) or time.monotonic() >= deadline:
                raise
    return value


def is_transient(exc: BaseException) -> bool:
    """A rate limit, server or network error worth retrying while waiting."""
    import httpx
    from foundry_sdk import _errors as sdk

    transient = (
        sdk.RateLimitError,
        sdk.ServiceUnavailable,
        sdk.InternalServerError,
        sdk.ConnectionError,
        sdk.TimeoutError,
        httpx.TransportError,
    )
    return isinstance(exc, transient)
