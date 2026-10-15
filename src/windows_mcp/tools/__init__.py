"""tools subpackage — registers all MCP tool definitions on a FastMCP instance."""

from windows_mcp.tools import (
    app,
    clipboard,
    control_status,
    display,
    filesystem,
    input,
    multi,
    notification,
    process,
    registry,
    scrape,
    shell,
    snapshot,
)

_MODULES = [
    control_status,
    app,
    display,
    shell,
    filesystem,
    snapshot,
    input,
    scrape,
    multi,
    clipboard,
    process,
    notification,
    registry,
]


def register_all(mcp, *, get_desktop):
    """Register every tool module on *mcp*.

    *get_desktop* is a zero-arg callable that returns the current
    ``Desktop`` instance (resolved lazily so that tools can be registered before ``lifespan`` initializes the singletons).
    """
    for mod in _MODULES:
        mod.register(mcp, get_desktop=get_desktop)
