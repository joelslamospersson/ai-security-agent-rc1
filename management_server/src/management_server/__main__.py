"""
Entry point for the Management Server.

Usage:
    python -m management_server
    python -m management_server --help
"""

from __future__ import annotations

import argparse


def main() -> None:
    """Parse arguments and start the Management Server."""
    parser = argparse.ArgumentParser(
        prog="management-server",
        description="AI Security Management Server",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Bind address (default: from settings)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port (default: from settings)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (development only)",
    )
    args = parser.parse_args()

    from management_server.config.settings import get_settings

    settings = get_settings()
    host = args.host or settings.host
    port = args.port or settings.port

    import uvicorn

    uvicorn.run(
        "management_server.app:create_app",
        host=host,
        port=port,
        reload=args.reload,
        log_level=settings.log_level.lower(),
        factory=True,
    )


if __name__ == "__main__":
    main()
