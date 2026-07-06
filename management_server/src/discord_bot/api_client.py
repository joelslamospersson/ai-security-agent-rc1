"""
Management Server API client — the ONLY way the Discord Adapter communicates
with the Management Server. Never queries the database directly.
"""

from __future__ import annotations

from typing import Any

import aiohttp
import structlog

from discord_bot.exceptions import APIClientError

logger = structlog.get_logger("discord_bot.api_client")

API_PREFIX = "/api/v1"


class ManagementAPIClient:
    """HTTP client for the Management Server REST API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str = "",
        timeout_seconds: int = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> ManagementAPIClient:
        self._session = aiohttp.ClientSession(
            base_url=self._base_url,
            timeout=self._timeout,
            headers=self._build_headers(),
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                base_url=self._base_url,
                timeout=self._timeout,
                headers=self._build_headers(),
            )
        return self._session

    async def health_check(self) -> dict[str, Any]:
        """Check Management Server health."""
        return await self._get("/health")

    async def get_metrics(self) -> dict[str, Any]:
        """Get aggregated server metrics."""
        results: dict[str, Any] = {}
        try:
            results["heartbeat"] = await self._get(f"{API_PREFIX}/heartbeat/metrics")
        except APIClientError:
            results["heartbeat"] = {}
        try:
            results["machines"] = await self._get(f"{API_PREFIX}/machines")
        except APIClientError:
            results["machines"] = {}
        try:
            results["policies"] = await self._get(f"{API_PREFIX}/policies")
        except APIClientError:
            results["policies"] = []
        try:
            results["notifications"] = await self._get(f"{API_PREFIX}/notifications/queue")
        except APIClientError:
            results["notifications"] = {}
        return results

    async def register_guild(self, guild_id: str, name: str) -> dict[str, Any]:
        """Register a Discord guild with the Management Server."""
        return await self._post(
            f"{API_PREFIX}/discord/guilds",
            json={"guild_id": guild_id, "name": name},
        )

    async def get_pending_notifications(self) -> list[dict[str, Any]]:
        """Get pending notifications from the queue."""
        try:
            result = await self._get(f"{API_PREFIX}/notifications?status=pending&limit=50")
            pending: list[dict[str, Any]] = result.get("notifications", [])
            return pending
        except APIClientError:
            return []

    async def record_audit_event(self, event: dict[str, Any]) -> None:
        """Record an audit event via the Management Server API."""
        try:
            await self._post(f"{API_PREFIX}/audit", json=event)
        except APIClientError:
            logger.warning("Failed to record audit event", event_type=event.get("event_type"))

    async def _get(self, path: str) -> dict[str, Any]:
        session = await self._ensure_session()
        async with session.get(path) as resp:
            if resp.status >= 400:
                raise APIClientError(path, resp.status, await resp.text())
            json_data: dict[str, Any] = await resp.json()
            return json_data

    async def _post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        session = await self._ensure_session()
        async with session.post(path, json=json) as resp:
            if resp.status >= 400:
                raise APIClientError(path, resp.status, await resp.text())
            json_data: dict[str, Any] = await resp.json()
            return json_data
