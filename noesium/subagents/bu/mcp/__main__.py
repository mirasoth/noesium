"""Entry point for running MCP server as a module.

Usage:
    python -m noesium.subagents.bu.mcp.server
"""

import asyncio

from .server import main

if __name__ == "__main__":
    asyncio.run(main())
