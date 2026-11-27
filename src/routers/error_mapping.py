"""Turn domain errors into the one error shape the host sees.

With `mask_error_details=True` FastMCP replaces every exception by a generic message, except
`ToolError`. It does so *inside* the tool call, before any middleware runs, so a middleware
never sees our domain errors. The translation has to happen inside the tool, which is why it
is a decorator applied by `register_mcp_tools` to every tool it registers.
"""

import functools
from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastmcp.exceptions import ToolError

from src.core.errors import DomainError


def maps_domain_errors[F: Callable[..., Awaitable[Any]]](tool: F) -> F:
    """Raise `ToolError("[CODE] message")` for a domain error; leave anything else to be masked.

    The stable code goes first so a host or a test can tell errors apart without parsing prose.
    """

    @functools.wraps(tool)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await tool(*args, **kwargs)
        except DomainError as error:
            raise ToolError(f"[{error.error_code}] {error}") from error

    return cast(F, wrapper)  # same signature (`wraps`), which is what FastMCP reads
