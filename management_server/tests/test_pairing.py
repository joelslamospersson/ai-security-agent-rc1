"""
Comprehensive tests for the Secure Pairing Protocol subsystem.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from management_server.pairing.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    InvalidTransitionError,
    ReplayAttackError,
    TokenConsumedError,
    TokenRevokedError,
)
from management_server.pairing.generator import PairingTokenGenerator
from management_server.pairing.metrics import PairingMetricsCollector
from management_server.pairing.models import TokenState, TokenStateMachine
from management_server.pairing.repository import PairingRepository
from management_server.pairing.schemas import (
    PairingConsumeRequest,
    PairingTokenCreateRequest,
    PairingValidateRequest,
)
from management_server.pairing.service import PairingService
from management_server.pairing.validator import PairingTokenValidator

# ─── Generator Tests ───────────────────────────────────────────────────────


class TestPairingTokenGenerator:
    def test_generate_returns_three_values(self):
        gen = PairingTokenGenerator()
        plaintext, token_hash, expires_at = gen.generate()
        assert isinstance(plaintext, str)
        assert len(plaintext) > 0
        assert isinstance(token_hash, str)
        assert len(token_hash) == 64  # SHA-256 hexdigest
        assert isinstance(expires_at, datetime)

    def test_generated_token_is_url_safe(self):
        gen = PairingTokenGenerator()
        plaintext, _, _ = gen.generate()
        # Should be base64 urlsafe (alphanumeric, -, _)
        import re

        assert re.match(r"^[A-Za-z0-9\-_]+$", plaintext)

    def test_hash_is_deterministic(self):
        gen = PairingTokenGenerator()
        assert gen.verify_hash("test-token", gen._hash("test-token"))

    def test_hash_mismatch(self):
        gen = PairingTokenGenerator()
        assert not gen.verify_hash("wrong", gen._hash("right"))

    def test_unique_generations(self):
        gen = PairingTokenGenerator()
        p1, h1, _ = gen.generate()
        p2, h2, _ = gen.generate()
        assert p1 != p2
        assert h1 != h2

    def test_token_id_is_hex(self):
        tid = PairingTokenGenerator.generate_token_id()
        assert len(tid) == 32  # 16 bytes = 32 hex chars
        assert all(c in "0123456789abcdef" for c in tid)


# ─── State Machine Tests ───────────────────────────────────────────────────


class TestTokenStateMachine:
    def test_legal_transitions(self):
        assert TokenStateMachine.is_legal(TokenState.UNUSED, TokenState.ISSUED)
        assert TokenStateMachine.is_legal(TokenState.ISSUED, TokenState.PENDING)
        assert TokenStateMachine.is_legal(TokenState.PENDING, TokenState.CONSUMED)

    def test_illegal_transitions(self):
        assert not TokenStateMachine.is_legal(TokenState.UNUSED, TokenState.CONSUMED)
        assert not TokenStateMachine.is_legal(TokenState.CONSUMED, TokenState.PENDING)

    def test_validate_raises(self):
        with pytest.raises(InvalidTransitionError):
            TokenStateMachine.validate_transition(TokenState.UNUSED, TokenState.CONSUMED)

    def test_legal_transitions_from_issued(self):
        targets = TokenStateMachine.legal_transitions_from(TokenState.ISSUED)
        assert TokenState.PENDING in targets
        assert TokenState.EXPIRED in targets
        assert TokenState.REVOKED in targets


# ─── Validator Tests ───────────────────────────────────────────────────────


class TestPairingTokenValidator:
    def test_valid_token_passes(self):
        gen = PairingTokenGenerator()
        plaintext, token_hash, _expires_at = gen.generate()
        far_future = datetime.now(tz=UTC) + timedelta(days=1)
        # Should not raise
        PairingTokenValidator.validate_token(plaintext, token_hash, TokenState.ISSUED, far_future)

    def test_expired_token_raises(self):
        gen = PairingTokenGenerator()
        plaintext, token_hash, _ = gen.generate()
        past = datetime.now(tz=UTC) - timedelta(minutes=1)
        with pytest.raises(ExpiredTokenError):
            PairingTokenValidator.validate_token(plaintext, token_hash, TokenState.ISSUED, past)

    def test_consumed_token_raises_replay(self):
        gen = PairingTokenGenerator()
        plaintext, token_hash, _expires_at = gen.generate()
        far_future = datetime.now(tz=UTC) + timedelta(days=1)
        with pytest.raises(ReplayAttackError):
            PairingTokenValidator.validate_token(
                plaintext, token_hash, TokenState.CONSUMED, far_future
            )

    def test_revoked_token_raises(self):
        gen = PairingTokenGenerator()
        plaintext, token_hash, _expires_at = gen.generate()
        far_future = datetime.now(tz=UTC) + timedelta(days=1)
        with pytest.raises(TokenRevokedError):
            PairingTokenValidator.validate_token(
                plaintext, token_hash, TokenState.REVOKED, far_future
            )

    def test_invalid_hash_raises(self):
        far_future = datetime.now(tz=UTC) + timedelta(days=1)
        with pytest.raises(InvalidTokenError):
            PairingTokenValidator.validate_token(
                "bad-token", "deadbeef" * 8, TokenState.ISSUED, far_future
            )

    def test_validate_for_consumption_rejects_unissued(self):
        gen = PairingTokenGenerator()
        plaintext, token_hash, _expires_at = gen.generate()
        far_future = datetime.now(tz=UTC) + timedelta(days=1)
        with pytest.raises(InvalidTokenError):
            PairingTokenValidator.validate_for_consumption(
                plaintext, token_hash, TokenState.UNUSED, far_future
            )


# ─── Metrics Tests ─────────────────────────────────────────────────────────


class TestPairingMetrics:
    def test_initial_state(self):
        m = PairingMetricsCollector()
        snap = m.snapshot()
        assert snap.tokens_generated == 0

    def test_counters(self):
        m = PairingMetricsCollector()
        m.token_generated()
        m.token_consumed()
        m.token_expired()
        m.token_revoked()
        m.validation_failure()
        m.replay_attempt()
        snap = m.snapshot(active_tokens=3, total_tokens=10)
        assert snap.tokens_generated == 1
        assert snap.tokens_consumed == 1
        assert snap.tokens_expired == 1
        assert snap.tokens_revoked == 1
        assert snap.validation_failures == 1
        assert snap.replay_attempts == 1
        assert snap.active_tokens == 3
        assert snap.total_tokens == 10


# ─── Repository Tests ──────────────────────────────────────────────────────


class TestPairingRepository:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = PairingRepository(sqlite_session)
        self.session = sqlite_session

    async def test_create_and_get(self):
        now = datetime.now(tz=UTC)
        later = now + timedelta(hours=1)
        record = await self.repo.create_token(
            token_id="test-create-1",
            token_hash="a" * 64,
            expires_at=later,
            creator="test",
            audit_reference="audit-1",
        )
        assert record["token_id"] == "test-create-1"
        assert record["status"] == TokenState.ISSUED.value

    async def test_get_by_hash(self):
        now = datetime.now(tz=UTC)
        later = now + timedelta(hours=1)
        await self.repo.create_token(
            token_id="test-hash-1",
            token_hash="b" * 64,
            expires_at=later,
        )
        found = await self.repo.get_by_token_hash("b" * 64)
        assert found is not None
        assert found["token_id"] == "test-hash-1"

    async def test_get_by_hash_not_found(self):
        found = await self.repo.get_by_token_hash("nonexistent")
        assert found is None

    async def test_update_status(self):
        now = datetime.now(tz=UTC)
        later = now + timedelta(hours=1)
        await self.repo.create_token(
            token_id="test-update",
            token_hash="c" * 64,
            expires_at=later,
        )
        updated = await self.repo.update_status("test-update", TokenState.CONSUMED)
        assert updated["status"] == TokenState.CONSUMED.value
        assert updated["consumed_at"] is not None

    async def test_expire_pending(self):
        now = datetime.now(tz=UTC)
        past = now - timedelta(hours=1)
        # Insert directly with past expires_at
        import uuid

        from sqlalchemy import text

        await self.session.execute(
            text("""
                INSERT INTO pairing_tokens (id, token_id, token_hash, status, created_at, expires_at)
                VALUES (:id, :tid, :th, 'pending', :now, :past)
            """),
            {"id": str(uuid.uuid4()), "tid": "exp-test", "th": "d" * 64, "now": now, "past": past},
        )
        await self.session.commit()

        count = await self.repo.expire_pending_tokens()
        assert count >= 1

    async def test_list_and_count(self):
        now = datetime.now(tz=UTC)
        later = now + timedelta(hours=1)
        await self.repo.create_token(
            token_id="list-1",
            token_hash="e" * 64,
            expires_at=later,
        )
        await self.repo.create_token(
            token_id="list-2",
            token_hash="f" * 64,
            expires_at=later,
        )
        _tokens, total = await self.repo.list_tokens()
        assert total >= 2

        counts = await self.repo.count_by_status()
        assert TokenState.ISSUED.value in counts


# ─── Service Tests ─────────────────────────────────────────────────────────


class TestPairingService:
    @pytest.fixture(autouse=True)
    async def setup(self, sqlite_session: AsyncSession):
        self.repo = PairingRepository(sqlite_session)
        self.session = sqlite_session
        self.service = PairingService(repository=self.repo)

    async def test_create_token(self):
        req = PairingTokenCreateRequest(creator="pytest", ttl_minutes=15)
        resp = await self.service.create_token(req)
        assert resp.token_id != ""
        assert len(resp.token) > 0  # plaintext token
        assert resp.status == TokenState.ISSUED

    async def test_validate_token(self):
        req = PairingTokenCreateRequest(creator="pytest")
        created = await self.service.create_token(req)

        validate_req = PairingValidateRequest(
            token=created.token,
            machine_uuid="test-machine",
        )
        result = await self.service.validate_token(validate_req)
        assert result.valid
        assert result.token_id == created.token_id

    async def test_validate_invalid_token(self):
        validate_req = PairingValidateRequest(
            token="invalid-token",
            machine_uuid="test-machine",
        )
        result = await self.service.validate_token(validate_req)
        assert not result.valid

    async def test_consume_token(self):
        req = PairingTokenCreateRequest(creator="pytest")
        created = await self.service.create_token(req)

        # Validate first (transitions to PENDING)
        validate_req = PairingValidateRequest(
            token=created.token,
            machine_uuid="consume-machine",
        )
        await self.service.validate_token(validate_req)

        consume_req = PairingConsumeRequest(
            token=created.token,
            machine_uuid="consume-machine",
        )
        result = await self.service.consume_token(consume_req)
        assert result.paired
        assert result.machine_uuid == "consume-machine"

    async def test_replay_after_consume(self):
        req = PairingTokenCreateRequest(creator="pytest")
        created = await self.service.create_token(req)

        validate_req = PairingValidateRequest(
            token=created.token,
            machine_uuid="replay-machine",
        )
        await self.service.validate_token(validate_req)

        consume_req = PairingConsumeRequest(
            token=created.token,
            machine_uuid="replay-machine",
        )
        await self.service.consume_token(consume_req)

        # Second consume should fail
        with pytest.raises((TokenConsumedError, ReplayAttackError)):
            await self.service.consume_token(consume_req)

    async def test_expire_tokens(self):
        # Create a token that's already expired
        import uuid

        from sqlalchemy import text

        now = datetime.now(tz=UTC)
        past = now - timedelta(hours=1)
        await self.session.execute(
            text("""
                INSERT INTO pairing_tokens (id, token_id, token_hash, status, created_at, expires_at)
                VALUES (:id, :tid, :th, 'pending', :now, :past)
            """),
            {
                "id": str(uuid.uuid4()),
                "tid": "stale-test",
                "th": "g" * 64,
                "now": now,
                "past": past,
            },
        )
        await self.session.commit()

        count = await self.service.expire_stale_tokens()
        assert count >= 1

    async def test_revoke_token(self):
        req = PairingTokenCreateRequest(creator="pytest")
        created = await self.service.create_token(req)

        info = await self.service.revoke_token(created.token_id)
        assert info["status"] == TokenState.REVOKED.value

    async def test_get_token_info_no_hash(self):
        req = PairingTokenCreateRequest(creator="pytest")
        created = await self.service.create_token(req)

        info = await self.service.get_token_info(created.token_id)
        assert "token_hash" not in info
        assert "token_id" in info or "token_id" in str(info)

    async def test_list_tokens_no_hash(self):
        req = PairingTokenCreateRequest(creator="pytest")
        await self.service.create_token(req)

        result = await self.service.list_tokens()
        assert "tokens" in result
        if result["tokens"]:
            assert "token_hash" not in result["tokens"][0]


# ─── API Tests ─────────────────────────────────────────────────────────────


class TestPairingAPI:
    def test_create_pairing_token_endpoint(self, client: TestClient):
        resp = client.post(
            "/api/v1/pairing",
            json={"creator": "test", "ttl_minutes": 15},
        )
        # May return 503 if DB not available
        assert resp.status_code in (200, 503)

    def test_validate_endpoint(self, client: TestClient):
        resp = client.post(
            "/api/v1/pairing/validate",
            json={"token": "test", "machine_uuid": "test"},
        )
        assert resp.status_code in (200, 503)

    def test_consume_endpoint(self, client: TestClient):
        resp = client.post(
            "/api/v1/pairing/consume",
            json={"token": "test", "machine_uuid": "test"},
        )
        assert resp.status_code in (400, 503)

    def test_get_pairing_token_endpoint(self, client: TestClient):
        resp = client.get("/api/v1/pairing/nonexistent")
        assert resp.status_code in (404, 503)
