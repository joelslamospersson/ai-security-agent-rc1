"""
Entry point for the AI Security Agent.

Usage:
    python -m security_agent
    python -m security_agent --help
    python -m security_agent --version
    python -m security_agent --dev          # Developer mode
    python -m security_agent --init-db      # Initialize database only
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from security_agent import __version__


def main() -> None:
    """Parse arguments and launch the agent."""
    parser = argparse.ArgumentParser(
        prog="security-agent",
        description="Intelligent real-time Linux security agent",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("/etc/ai-security-agent/config.yaml"),
        help="Path to configuration file (default: /etc/ai-security-agent/config.yaml)",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable developer mode (see --dev-help)",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database schema and exit",
    )
    parser.add_argument(
        "--dev-help",
        action="store_true",
        help="Show developer mode usage",
    )

    args = parser.parse_args()

    if args.dev_help:
        _show_dev_help()
        sys.exit(0)

    # Delegate to application lifecycle
    from security_agent.app import Application

    app = Application(config_path=args.config, dev_mode=args.dev)

    if args.init_db:
        asyncio.run(app.initialize_database())
        print("[+] Database initialized.")
        sys.exit(0)

    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("\n[+] Agent stopped by user.")
        sys.exit(0)


def _show_dev_help() -> None:
    """Show developer mode usage information."""
    print("""
Developer Mode Commands
=======================
  python -m security_agent --dev replay <path>  [--rate N]
  python -m security_agent --dev inject         [--type TYPE --ip IP --count N]
  python -m security_agent --dev attack <name>  [ssh-brute|port-scan|...]
  python -m security_agent --dev benchmark      [--detector NAME --events N]
  python -m security_agent --dev profile        [--mode memory|cpu --duration N]
  python -m security_agent --dev validate-rules

See https://github.com/joelslamospersson/ai-security-agent-rc1 for full documentation.
""")


if __name__ == "__main__":
    main()
