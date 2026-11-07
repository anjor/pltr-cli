"""Turn SDK results into JSON documents.

The JSON contract (global decision 1): ``--format json`` prints the SDK's own
serialization of a result, i.e. ``model.model_dump(mode="json", by_alias=True,
exclude_none=True)``: Foundry API field names (camelCase), null fields
omitted, JSON-safe values (datetimes as ISO-8601 strings). Lists use the API's
paged shape ``{"data": [...], "nextPageToken": "..."}``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from .runtime import warn


@dataclass
class Page:
    """One or more pages of a paged list, plus the token to resume from.

    Serializes to ``{"data": [...], "nextPageToken": "..."}``;
    ``nextPageToken`` is omitted when there are no more pages.
    """

    data: List[Any] = field(default_factory=list)
    next_page_token: Optional[str] = None


def _is_resource_iterator(value: Any) -> bool:
    # Imported lazily to keep `pltr --help` fast.
    from foundry_sdk._core.resource_iterator import ResourceIterator

    return isinstance(value, ResourceIterator)


def _finite(value: Any) -> Any:
    """Replace NaN/Infinity (not valid JSON) with None, recursively."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _finite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_finite(item) for item in value]
    return value


def to_jsonable(value: Any) -> Any:
    """Convert a result into plain JSON-compatible Python data.

    Handles SDK pydantic models (``model_dump(mode="json", by_alias=True,
    exclude_none=True)`` semantics, also when nested inside dicts and lists),
    plain dicts (SDK ontology objects are dicts; their keys and values are
    kept as they are, apart from making values JSON-safe), lists, tuples,
    sets, datetimes, enums, primitives and ``None``. A :class:`Page` or an
    SDK ``ResourceIterator`` becomes the paged shape for its current page.
    Unknown objects with a ``to_dict()`` method are serialized through it;
    anything else unknown becomes ``str(value)``.
    """
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return _finite(value)
    if isinstance(value, Page):
        return _paged(value.data, value.next_page_token)
    if _is_resource_iterator(value):
        return _paged(value.data, value.next_page_token)

    import pydantic
    import pydantic_core

    known = (pydantic.BaseModel, dict, list, tuple, set, frozenset)
    if not isinstance(value, known) and callable(getattr(value, "to_dict", None)):
        value = value.to_dict()

    return _finite(
        pydantic_core.to_jsonable_python(
            value, by_alias=True, exclude_none=True, serialize_unknown=True
        )
    )


def _paged(data: Any, next_page_token: Optional[str]) -> Dict[str, Any]:
    document: Dict[str, Any] = {"data": [to_jsonable(item) for item in data]}
    if next_page_token is not None:
        document["nextPageToken"] = next_page_token
    return document


def to_document(result: Any) -> Any:
    """Shape a command result as its JSON document.

    A list/tuple becomes ``{"data": [...]}`` (the API's paged shape); a
    :class:`Page` or ``ResourceIterator`` becomes ``{"data": [...],
    "nextPageToken": ...}``; anything else is :func:`to_jsonable` of itself
    (a single object is emitted as that object; ``None`` as ``null``).
    """
    if isinstance(result, (list, tuple)):
        return _paged(result, None)
    return to_jsonable(result)


def collect_pages(
    fetch_page: Callable[[Optional[str]], Any],
    *,
    page_token: Optional[str] = None,
    max_pages: Optional[int] = 1,
    all_pages: bool = False,
    stop_at_empty_page: bool = False,
) -> Page:
    """Fetch pages of a paged SDK list endpoint and merge them into a Page.

    ``fetch_page(token)`` must call the SDK for exactly one page starting at
    ``token`` and return an object with ``.data`` and ``.next_page_token``:
    an SDK ``ResourceIterator`` (constructing one fetches exactly one page,
    and it is never iterated here) or a paged response model such as
    ``SearchUsersResponse``. Example::

        page = collect_pages(
            lambda token: client.filesystem.Folder.children(
                folder_rid, page_size=page_size, page_token=token
            ),
            page_token=page_token, max_pages=max_pages, all_pages=all_pages,
        )

    Stops after ``max_pages`` pages (default 1) unless ``all_pages`` is set,
    and returns the token of the next unread page, if any.

    Some endpoints return a ``nextPageToken`` on every page, even when there
    is nothing more to read yet (audit log files without an end date, which
    clients poll for new files). With ``stop_at_empty_page`` paging also
    stops at the first page without items, and the returned token is that
    page's ``nextPageToken``, from which a later call picks up new items.

    Paging always stops, with a warning, when the API hands back a token
    that was already sent in this listing (the next request would fetch a
    page already read, forever); that token is returned.
    """
    items: List[Any] = []
    token = page_token
    sent: Set[Optional[str]] = set()
    pages = 0
    limit = None if all_pages else max_pages
    while True:
        sent.add(token)
        page = fetch_page(token)
        data = page.data or []
        items.extend(data)
        token = page.next_page_token
        pages += 1
        if not token or (limit is not None and pages >= limit):
            break
        if stop_at_empty_page and not data:
            break
        if token in sent:
            warn(
                f"Stopped paging after {pages} page(s): the API returned the page "
                f"token {token!r} again, so the next request would read a page "
                "already read."
            )
            break
    return Page(data=items, next_page_token=token or None)
