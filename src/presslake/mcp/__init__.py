"""MCP PressLake — outils search / read pour agents (module 14)."""

from presslake.mcp.server import create_server, run_stdio
from presslake.mcp.tools import read_silver, search_corpus

__all__ = ["create_server", "read_silver", "run_stdio", "search_corpus"]
