"""
CLI option utilities and decorators for common command parameters.

This module provides reusable decorators for adding standard options
to CLI commands, ensuring consistency across the application.
"""

from functools import wraps
from typing import Any, Callable, Dict, Optional
import typer


def pagination_options(include_token: bool = True) -> Callable:
    """
    Decorator to add standard pagination options to a command.

    This decorator adds the following options to a command:
    - --page-size: Number of items per page
    - --max-pages: Maximum number of pages to fetch
    - --page-token: Token to resume from (if include_token=True)
    - --all: Fetch all available pages

    Args:
        include_token: Whether to include --page-token option
                      (True for response-based, False for some iterator-based commands)

    Returns:
        Decorator function

    Example:
        >>> @app.command("list")
        >>> @pagination_options(include_token=True)
        >>> def list_users(page_size, max_pages, page_token, all, ...):
        ...     pass

    Note:
        The decorated command function must accept keyword arguments for:
        - page_size: Optional[int]
        - max_pages: Optional[int]
        - all: bool
        - page_token: Optional[str] (if include_token=True)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Add pagination options as function annotations
        # Note: Typer processes these annotations to create CLI options

        # Get current annotations
        annotations = getattr(func, "__annotations__", {})

        # Add page_size option
        wrapper.__annotations__ = {
            **annotations,
            "page_size": Optional[int],
            "max_pages": Optional[int],
            "all": bool,
        }

        if include_token:
            wrapper.__annotations__["page_token"] = Optional[str]

        # Add default values via Typer.Option
        # We'll use a parameter injection approach
        orig_func = func

        def injected_wrapper(
            *args,
            page_size: Optional[int] = typer.Option(
                None,
                "--page-size",
                help="Number of items per page (default: from settings)",
            ),
            max_pages: Optional[int] = typer.Option(
                1, "--max-pages", help="Maximum number of pages to fetch (default: 1)"
            ),
            all: bool = typer.Option(
                False, "--all", help="Fetch all available pages (overrides --max-pages)"
            ),
            page_token: Optional[str] = typer.Option(
                None, "--page-token", help="Page token to resume from previous response"
            )
            if include_token
            else None,
            **kwargs,
        ):
            # Build kwargs with pagination options
            pagination_kwargs: Dict[str, Any] = {
                "page_size": page_size,
                "max_pages": max_pages,
                "all": all,
            }
            if include_token:
                pagination_kwargs["page_token"] = page_token

            # Merge with existing kwargs
            all_kwargs = {**kwargs, **pagination_kwargs}

            return orig_func(*args, **all_kwargs)

        # Preserve function metadata
        injected_wrapper.__name__ = orig_func.__name__
        injected_wrapper.__doc__ = orig_func.__doc__
        injected_wrapper.__module__ = orig_func.__module__
        injected_wrapper.__qualname__ = orig_func.__qualname__
        injected_wrapper.__annotations__ = orig_func.__annotations__

        return injected_wrapper

    return decorator
