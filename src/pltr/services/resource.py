"""
Resource service wrapper for the Foundry SDK filesystem API.

Every ``Resource`` endpoint pltr uses is GA, so no call passes ``preview``.
Methods return SDK models (or SDK iterators) unchanged and let SDK exceptions
propagate so the error layer can classify them.
"""

import functools
import typing
from collections import deque
from dataclasses import dataclass, field
from typing import Any, List, Optional, Set, Tuple

from ..contract import Page
from ..contract.resources import is_path
from .base import BaseService

#: RID of the root folder. Its children are the spaces, but the API can't get
#: or list it: Foundry answers ``GetRootFolderNotSupported`` (HTTP 400).
ROOT_FOLDER_RID = "ri.compass.main.folder.0"

#: Why a command can't take the root folder, and what to use instead.
ROOT_FOLDER_UNSUPPORTED = (
    f"the Foundry API can't get or list the root folder ({ROOT_FOLDER_RID}). "
    "Its children are the spaces: run 'pltr space list', then pass a space, "
    "project or folder RID"
)

#: Maximum number of resources or paths per batch request.
MAX_BATCH_SIZE = 1000

#: Default number of folders ``resource search`` lists before it stops.
DEFAULT_MAX_SEARCH_FOLDERS = 1000

#: The resource type of folders (including projects); ``search`` descends into them.
FOLDER_TYPE = "COMPASS_FOLDER"

#: Short names accepted by ``--type`` (earlier releases documented them).
TYPE_ALIASES = {"DATASET": "FOUNDRY_DATASET", "FOLDER": "COMPASS_FOLDER"}

#: Most seconds between two polls of ``resource wait``: one cheap GET, for
#: something (code repository checks) that takes minutes, not hours (#219).
WAIT_MAX_POLL = 10.0


def format_seconds(seconds: float) -> str:
    """``600``, ``2.5``: a --timeout as the user would type it."""
    return str(int(seconds)) if float(seconds).is_integer() else repr(float(seconds))


def _literal_values(tp: Any) -> List[str]:
    """String values of a (possibly ``Annotated``) ``Literal`` type alias."""
    values: List[str] = []
    for arg in typing.get_args(tp):
        if isinstance(arg, str):
            values.append(arg)
        else:
            values.extend(_literal_values(arg))
    return values


@functools.lru_cache(maxsize=None)
def resource_types() -> Tuple[str, ...]:
    """Every resource type the installed SDK knows (``ResourceType``)."""
    from foundry_sdk.v2.filesystem.models import ResourceType

    return tuple(_literal_values(ResourceType))


def normalize_resource_type(value: str) -> str:
    """Return the API name of a resource type given case-insensitively.

    Accepts the SDK's ``ResourceType`` values (``FOUNDRY_DATASET``,
    ``COMPASS_FOLDER``, ...) and the short names ``dataset`` and ``folder``.

    Raises:
        ValueError: if the SDK doesn't know the type.
    """
    name = value.strip().upper().replace("-", "_")
    name = TYPE_ALIASES.get(name, name)
    if name not in resource_types():
        raise ValueError(name)
    return name


@dataclass
class SearchResult:
    """Matches of :meth:`ResourceService.search_resources` and how far it got."""

    matches: List[Any] = field(default_factory=list)
    folders_scanned: int = 0
    #: True when the folder limit stopped the scan before every folder was read.
    truncated: bool = False


def resource_matches(resource: Any, needle: str) -> bool:
    """True when ``needle`` (lower case) occurs in a resource's name, path,
    description, RID or type."""
    haystack = (
        resource.display_name,
        resource.path,
        resource.description,
        resource.rid,
        resource.type,
    )
    return any(needle in str(part).lower() for part in haystack if part)


class ResourceService(BaseService):
    """Service wrapper for Foundry resource operations (``client.filesystem``)."""

    def _get_service(self) -> Any:
        """Get the Foundry filesystem service."""
        return self.client.filesystem

    def get_resource(self, resource_rid: str) -> Any:
        """Get a resource (``Resource.get``, GA); returns a ``Resource`` model."""
        return self.service.Resource.get(resource_rid)

    def get_resource_by_path(self, path: str) -> Any:
        """Get a resource by absolute path (``Resource.get_by_path``, GA)."""
        return self.service.Resource.get_by_path(path=path)

    def find_resource(self, resource: str) -> Optional[Any]:
        """The resource at a Compass path or RID, or ``None`` while there is none.

        Only the API's answers for a resource that doesn't exist (or that the
        account can't see) mean ``None``: 404 ``PathNotFound`` for a path and
        404 ``ResourceNotFound`` for a RID. Every other error is raised.
        """
        from foundry_sdk.v2.filesystem import errors as filesystem_errors

        try:
            if is_path(resource):
                return self.get_resource_by_path(resource)
            return self.get_resource(resource)
        except (filesystem_errors.PathNotFound, filesystem_errors.ResourceNotFound):
            return None

    def wait_for_resource(self, resource: str, *, timeout: float, resume: str) -> Any:
        """Poll until a resource exists at a Compass path or RID (#219).

        Backoff as for ``--wait`` (``pltr.services.waiting``), but at most
        ``WAIT_MAX_POLL`` seconds between calls. After the first call, rate
        limits, 5xx and network errors are retried until the deadline; other
        errors are raised at once.

        Args:
            resume: the command line that waits again, for the timeout error.

        Raises:
            WaitTimedOut: (exit 9) still nothing after ``timeout`` seconds.
        """
        from ..contract import WaitTimedOut
        from .waiting import wait_until

        seconds = format_seconds(timeout)

        def timed_out(_: Any) -> Exception:
            if is_path(resource):
                message = f"No resource at {resource!r} after {seconds} seconds."
                parameters = {"path": resource}
                hint = (
                    "It may not exist yet (after a git push, a code repository's "
                    "checks create a transform's output dataset, which can take "
                    "a few minutes), or your account can't see it, or the path "
                    "has a typo. Wait again, or check the path."
                )
            else:
                message = f"Resource {resource} doesn't exist after {seconds} seconds."
                parameters = {"resourceRid": resource}
                hint = (
                    "A resource gets its RID when it is created, so check the "
                    "RID, or that your account can see it. To wait for "
                    "something that doesn't exist yet, wait for its path."
                )
            return WaitTimedOut(
                message,
                hint=hint,
                suggested_command=resume,
                parameters=parameters,
            )

        return wait_until(
            lambda: self.find_resource(resource),
            lambda found: found is not None,
            timeout=timeout,
            on_timeout=timed_out,
            max_poll=WAIT_MAX_POLL,
        )

    def list_children(
        self,
        folder_rid: str,
        resource_type: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of a folder's children (``Folder.children``, GA).

        Args:
            folder_rid: RID of the folder, project or space
            resource_type: keep only resources of this API type (filtered
                locally: the API has no type filter, so a page can hold
                fewer items than ``page_size``)

        Returns:
            Without ``resource_type``, the SDK ``ResourceIterator[Resource]``
            (constructing it fetched one page). With it, a ``Page`` of the
            matching resources and the same ``next_page_token``.
        """
        children = self.service.Folder.children(
            folder_rid, page_size=page_size, page_token=page_token
        )
        if resource_type is None:
            return children
        return Page(
            data=[child for child in children.data if child.type == resource_type],
            next_page_token=children.next_page_token,
        )

    def get_resources_batch(self, resource_rids: List[str]) -> Any:
        """Get up to 1000 resources in one request (``Resource.get_batch``, GA).

        Returns:
            ``GetResourcesBatchResponse``; its ``data`` maps RID to
            ``Resource``. RIDs that don't exist, or that are spaces or the
            root folder, are left out.
        """
        if len(resource_rids) > MAX_BATCH_SIZE:
            raise ValueError(f"Maximum batch size is {MAX_BATCH_SIZE} resources")
        from foundry_sdk.v2.filesystem.models import GetResourcesBatchRequestElement

        elements = [
            GetResourcesBatchRequestElement(resource_rid=rid) for rid in resource_rids
        ]
        return self.service.Resource.get_batch(body=elements)

    def get_resources_by_path_batch(self, paths: List[str]) -> Any:
        """Get up to 1000 resources by path (``Resource.get_by_path_batch``, GA).

        Returns:
            ``GetByPathResourcesBatchResponse``; its ``data`` lists the
            resources found. Paths that don't exist or can't be read are
            left out.
        """
        if len(paths) > MAX_BATCH_SIZE:
            raise ValueError(f"Maximum batch size is {MAX_BATCH_SIZE} paths")
        from foundry_sdk.v2.filesystem.models import (
            GetByPathResourcesBatchRequestElement,
        )

        elements = [GetByPathResourcesBatchRequestElement(path=path) for path in paths]
        return self.service.Resource.get_by_path_batch(body=elements)

    def search_resources(
        self,
        query: str,
        folder_rid: str,
        resource_type: Optional[str] = None,
        limit: Optional[int] = None,
        max_folders: int = DEFAULT_MAX_SEARCH_FOLDERS,
    ) -> SearchResult:
        """Find resources by scanning folders (the API has no search endpoint).

        Lists the children of ``folder_rid`` and, breadth-first, of every
        folder below it with ``Folder.children`` (GA, every page), keeping
        resources whose display name, path, description, RID or type
        contains ``query`` (case-insensitive).

        Args:
            query: text to look for
            folder_rid: folder, project or space to start from
            resource_type: keep only resources of this API type
            limit: stop after this many matches
            max_folders: stop after listing this many folders; the result is
                then marked ``truncated``

        Returns:
            A :class:`SearchResult` with the matching ``Resource`` models.
        """
        needle = query.strip().lower()
        if not needle:
            raise ValueError("The search query is empty")
        result = SearchResult()
        pending = deque([folder_rid])
        queued: Set[str] = set(pending)
        while pending:
            if result.folders_scanned >= max_folders:
                result.truncated = True
                break
            current = pending.popleft()
            result.folders_scanned += 1
            for child in self.service.Folder.children(current):
                if (
                    resource_type is None or child.type == resource_type
                ) and resource_matches(child, needle):
                    result.matches.append(child)
                    if limit is not None and len(result.matches) >= limit:
                        return result
                if child.type == FOLDER_TYPE and child.rid not in queued:
                    queued.add(child.rid)
                    pending.append(child.rid)
        return result

    # ==================== Trash Operations ====================

    def delete_resource(self, resource_rid: str) -> None:
        """Move a resource to the trash (``Resource.delete``, GA)."""
        self.service.Resource.delete(resource_rid)

    def restore_resource(self, resource_rid: str) -> None:
        """Restore a resource and its directly trashed ancestors (``Resource.restore``, GA)."""
        self.service.Resource.restore(resource_rid)

    def permanently_delete_resource(self, resource_rid: str) -> None:
        """Permanently delete a trashed resource (``Resource.permanently_delete``, GA)."""
        self.service.Resource.permanently_delete(resource_rid)

    # ==================== Markings Operations ====================

    def add_markings(self, resource_rid: str, marking_ids: List[str]) -> None:
        """Add markings to a resource (``Resource.add_markings``, GA)."""
        self.service.Resource.add_markings(resource_rid, marking_ids=marking_ids)

    def remove_markings(self, resource_rid: str, marking_ids: List[str]) -> None:
        """Remove markings from a resource (``Resource.remove_markings``, GA)."""
        self.service.Resource.remove_markings(resource_rid, marking_ids=marking_ids)

    def list_markings(
        self,
        resource_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of the markings applied directly to a resource.

        ``Resource.markings`` (GA) returns marking IDs (strings).

        Returns:
            The SDK ``ResourceIterator[str]``; constructing it fetched one page.
        """
        return self.service.Resource.markings(
            resource_rid, page_size=page_size, page_token=page_token
        )

    # ==================== Access Requirements ====================

    def get_access_requirements(self, resource_rid: str) -> Any:
        """Organizations and markings needed to view a resource.

        ``Resource.get_access_requirements`` (GA); returns an
        ``AccessRequirements`` model.
        """
        return self.service.Resource.get_access_requirements(resource_rid)
