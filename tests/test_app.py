"""
Smoke tests for the application skeleton.

Verifies that the project structure, entry points, and basic lifecycle work.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from security_agent import __version__


class TestVersion:
    """Package metadata tests."""

    def test_version_is_string(self) -> None:
        """__version__ should be a valid string."""
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_format(self) -> None:
        """Version should follow semver-ish format."""
        parts = __version__.split(".")
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()


class TestEntryPoint:
    """Verify that the module can be imported and invoked."""

    def test_main_import(self) -> None:
        """__main__ module should import without error."""
        from security_agent import __main__

        assert __main__ is not None

    def test_main_has_main_function(self) -> None:
        """__main__ should define main()."""
        from security_agent.__main__ import main

        assert callable(main)


class TestApplicationSkeleton:
    """Application lifecycle smoke tests."""

    @pytest.mark.asyncio
    async def test_app_creates(self) -> None:
        """Application should instantiate."""
        from security_agent.app import Application

        app = Application(config_path=Path("/dev/null"), dev_mode=True)
        assert app is not None
        assert app._dev_mode is True

    @pytest.mark.asyncio
    async def test_component_base(self) -> None:
        """Component base class should start and stop."""
        from security_agent.app import Component

        comp = Component("test-component")
        assert comp.name == "test-component"
        assert not comp.is_running

        await comp.start()
        assert comp.is_running

        await comp.stop()
        assert not comp.is_running

    @pytest.mark.asyncio
    async def test_initialize_database(self, app_instance) -> None:
        """--init-db path should complete without error."""
        await app_instance.initialize_database()
        # State invariant: app still usable after init-db
        assert app_instance._config_path is not None
        assert app_instance._shutdown_event is not None

    def test_process_id(self) -> None:
        """process_id should return a positive integer on real systems."""
        from security_agent.app import process_id

        pid = process_id()
        assert isinstance(pid, int)
        assert pid > 0
