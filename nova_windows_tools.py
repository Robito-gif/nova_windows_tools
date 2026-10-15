# -*- coding: utf-8 -*-
"""Nova Windows Tools: Modern Windows power, display, MCP, and ecosystem platform."""

# Copyright (C) 2026 Robin Güneş
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, version 3 only.

from __future__ import annotations

import argparse
import sys

from nova.cli.app import NovaApp
from nova.core.constants import APP_NAME, APP_VERSION

# Re-export legacy interfaces for full backward compatibility
from easy_windows_tools import (
    LocalWebSocketManager,
    MCPManager,
    ScreenRecorder,
    KeepAwakeApp,
    run_mcp_server,
)

__all__ = [
    "NovaApp",
    "LocalWebSocketManager",
    "MCPManager",
    "ScreenRecorder",
    "KeepAwakeApp",
    "run_mcp_server",
    "main",
]


def main():
    """Main CLI entrypoint for Nova Windows Tools."""
    if len(sys.argv) >= 3 and sys.argv[1] == "--mcp-server":
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--mcp-server", required=True)
        parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
        parser.add_argument("--port", type=int, default=8800)
        args = parser.parse_args(sys.argv[1:])
        run_mcp_server(args.mcp_server, transport=args.transport, port=args.port)
    else:
        parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
        parser.add_argument("--low-resource", action="store_true", help="Düşük donanım ve pil tasarruf modu")
        parser.add_argument("--version", action="store_true", help="Sürüm bilgisini göster")
        args, remaining = parser.parse_known_args()

        if args.version:
            print(f"{APP_NAME} v{APP_VERSION}")
            return

        app = NovaApp(low_resource=args.low_resource)
        app.run()


if __name__ == "__main__":
    main()
