"""Test fixtures for the Management Server."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import create_async_engine

from management_server.app import create_app
from management_server.config.settings import Settings
from management_server.database.base import Base


@pytest.fixture
def test_settings() -> Settings:
    return Settings(debug=True, log_level="DEBUG", log_format="console")


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    app = create_app(settings=test_settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def sqlite_engine():
    """Create an in-memory SQLite engine with CA tables."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS certificate_authority (
                id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                key_type TEXT NOT NULL DEFAULT 'Ed25519',
                certificate_pem TEXT NOT NULL DEFAULT '',
                public_key_pem TEXT NOT NULL DEFAULT '',
                fingerprint TEXT NOT NULL DEFAULT '',
                serial TEXT NOT NULL DEFAULT '',
                not_before TIMESTAMP,
                not_after TIMESTAMP,
                is_root INTEGER DEFAULT 1,
                is_initialized INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )

        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS machine_certificates (
                id TEXT PRIMARY KEY,
                machine_uuid TEXT NOT NULL UNIQUE,
                serial TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL DEFAULT '',
                issued_at TIMESTAMP,
                expires_at TIMESTAMP,
                certificate_pem TEXT NOT NULL DEFAULT '',
                certificate_fingerprint TEXT NOT NULL DEFAULT '',
                public_key_pem TEXT NOT NULL DEFAULT '',
                public_key_fingerprint TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                revoked_at TIMESTAMP,
                revocation_reason TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )

        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS migration_history (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                checksum TEXT NOT NULL DEFAULT '',
                success INTEGER DEFAULT 1
            )
        """)
        )

        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )

        # Phase 4: Machine registry and registration tables
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS machines (
                id TEXT PRIMARY KEY,
                machine_uuid TEXT NOT NULL UNIQUE,
                hostname TEXT NOT NULL DEFAULT '',
                operating_system TEXT NOT NULL DEFAULT '',
                architecture TEXT NOT NULL DEFAULT '',
                environment TEXT NOT NULL DEFAULT 'production',
                agent_version TEXT NOT NULL DEFAULT '',
                public_key_fingerprint TEXT NOT NULL DEFAULT '',
                public_key_pem TEXT NOT NULL DEFAULT '',
                certificate_fingerprint TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'unknown',
                first_seen TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                last_status_change TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )

        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS registration_requests (
                id TEXT PRIMARY KEY,
                machine_uuid TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                public_key_pem TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )

        await conn.execute(
            sa_text("CREATE INDEX IF NOT EXISTS idx_machines_status ON machines(status)")
        )
        await conn.execute(
            sa_text("CREATE INDEX IF NOT EXISTS idx_machines_hostname ON machines(hostname)")
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_registration_machine ON registration_requests(machine_uuid)"
            )
        )

        # Phase 5: Pairing tokens table
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS pairing_tokens (
                id TEXT PRIMARY KEY,
                token_id TEXT NOT NULL UNIQUE,
                token_hash TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'issued',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                consumed_at TIMESTAMP,
                creator TEXT NOT NULL DEFAULT 'system',
                machine_uuid TEXT,
                audit_reference TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_pairing_tokens_hash ON pairing_tokens(token_hash)"
            )
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_pairing_tokens_status ON pairing_tokens(status)"
            )
        )

        # Phase 6: Heartbeat tables
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS heartbeats (
                id TEXT PRIMARY KEY,
                machine_uuid TEXT NOT NULL,
                protocol_version TEXT NOT NULL DEFAULT '1.0',
                agent_version TEXT NOT NULL DEFAULT '',
                hostname TEXT NOT NULL DEFAULT '',
                environment TEXT NOT NULL DEFAULT 'production',
                sequence_number INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'healthy',
                health_json TEXT NOT NULL DEFAULT '',
                capabilities_json TEXT NOT NULL DEFAULT '',
                queues_json TEXT NOT NULL DEFAULT '',
                security_json TEXT NOT NULL DEFAULT '',
                received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS machine_status (
                machine_uuid TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'unknown',
                last_heartbeat_at TIMESTAMP,
                protocol_version TEXT NOT NULL DEFAULT '',
                agent_version TEXT NOT NULL DEFAULT '',
                hostname TEXT NOT NULL DEFAULT '',
                environment TEXT NOT NULL DEFAULT '',
                last_sequence_number INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS capability_history (
                id TEXT PRIMARY KEY,
                machine_uuid TEXT NOT NULL,
                capability TEXT NOT NULL,
                change_type TEXT NOT NULL DEFAULT 'changed',
                old_value TEXT,
                new_value TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text("CREATE INDEX IF NOT EXISTS idx_heartbeats_machine ON heartbeats(machine_uuid)")
        )
        await conn.execute(
            sa_text("CREATE INDEX IF NOT EXISTS idx_heartbeats_received ON heartbeats(received_at)")
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_capability_machine ON capability_history(machine_uuid)"
            )
        )

        # Phase 7: Policy tables
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS policies (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL DEFAULT '',
                version TEXT NOT NULL DEFAULT '1',
                parent TEXT,
                checksum TEXT NOT NULL DEFAULT '',
                heartbeat_interval_seconds INTEGER NOT NULL DEFAULT 30,
                notification_retention_days INTEGER NOT NULL DEFAULT 30,
                log_retention_days INTEGER NOT NULL DEFAULT 90,
                ip_masking_enabled INTEGER NOT NULL DEFAULT 1,
                maintenance_mode INTEGER NOT NULL DEFAULT 0,
                allowed_protocol_versions TEXT NOT NULL DEFAULT '["1.0"]',
                feature_flags_json TEXT NOT NULL DEFAULT '{}',
                raw_yaml_json TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS machine_policy_assignments (
                id TEXT PRIMARY KEY,
                machine_uuid TEXT NOT NULL UNIQUE,
                policy_name TEXT NOT NULL,
                assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                assigned_by TEXT NOT NULL DEFAULT 'system'
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS machine_policy_overrides (
                id TEXT PRIMARY KEY,
                machine_uuid TEXT NOT NULL,
                policy_name TEXT NOT NULL DEFAULT '',
                key TEXT NOT NULL,
                value TEXT NOT NULL DEFAULT '',
                original_value TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL DEFAULT 'admin',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (machine_uuid, key)
            )
        """)
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_policy_assignments_machine ON machine_policy_assignments(machine_uuid)"
            )
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_policy_overrides_machine ON machine_policy_overrides(machine_uuid)"
            )
        )

        # Phase 8: Routing tables
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS routing_rules (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL DEFAULT '',
                event_types TEXT NOT NULL DEFAULT '["*"]',
                destinations TEXT NOT NULL DEFAULT '["console"]',
                priority TEXT NOT NULL DEFAULT 'normal',
                template TEXT NOT NULL DEFAULT 'detailed',
                rate_limit_profile TEXT NOT NULL DEFAULT 'normal',
                retention_policy TEXT NOT NULL DEFAULT 'standard',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS routing_decisions (
                id TEXT PRIMARY KEY,
                decision_id TEXT NOT NULL UNIQUE,
                machine_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                destinations TEXT NOT NULL DEFAULT '[]',
                priority TEXT NOT NULL DEFAULT 'normal',
                template TEXT NOT NULL DEFAULT 'detailed',
                rate_limit_profile TEXT NOT NULL DEFAULT 'normal',
                retention_policy TEXT NOT NULL DEFAULT 'standard',
                matched_rule TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_routing_decisions_machine ON routing_decisions(machine_id)"
            )
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_routing_decisions_created ON routing_decisions(created_at)"
            )
        )

        # Phase 9: Notification tables
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                notification_id TEXT NOT NULL UNIQUE,
                routing_decision_id TEXT NOT NULL DEFAULT '',
                machine_id TEXT NOT NULL DEFAULT '',
                event_type TEXT NOT NULL DEFAULT '',
                destination TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'normal',
                template TEXT NOT NULL DEFAULT 'detailed',
                payload TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS delivery_results (
                id TEXT PRIMARY KEY,
                notification_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'success',
                adapter TEXT NOT NULL DEFAULT '',
                latency_ms REAL NOT NULL DEFAULT 0.0,
                error_code TEXT NOT NULL DEFAULT '',
                error_message TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at)"
            )
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_delivery_results_notification ON delivery_results(notification_id)"
            )
        )

        # Phase 10: Audit events table
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                audit_id TEXT NOT NULL UNIQUE,
                correlation_id TEXT NOT NULL DEFAULT '',
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                machine_id TEXT NOT NULL DEFAULT '',
                subsystem TEXT NOT NULL DEFAULT '',
                actor TEXT NOT NULL DEFAULT 'system',
                event_type TEXT NOT NULL DEFAULT '',
                severity TEXT NOT NULL DEFAULT 'info',
                outcome TEXT NOT NULL DEFAULT 'success',
                description TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                current_hash TEXT NOT NULL DEFAULT '',
                previous_hash TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text("CREATE INDEX IF NOT EXISTS idx_audit_subsystem ON audit_events(subsystem)")
        )
        await conn.execute(
            sa_text("CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_events(event_type)")
        )
        await conn.execute(
            sa_text("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp)")
        )

        # Phase 12: Command tables
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS commands (
                id TEXT PRIMARY KEY,
                command_id TEXT NOT NULL UNIQUE,
                correlation_id TEXT NOT NULL DEFAULT '',
                machine_id TEXT NOT NULL DEFAULT '',
                command_type TEXT NOT NULL DEFAULT '',
                parameters_json TEXT NOT NULL DEFAULT '{}',
                priority TEXT NOT NULL DEFAULT 'normal',
                state TEXT NOT NULL DEFAULT 'created',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                requested_by TEXT NOT NULL DEFAULT 'system',
                created_at_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS command_lifecycle (
                id TEXT PRIMARY KEY,
                command_id TEXT NOT NULL,
                to_state TEXT NOT NULL DEFAULT '',
                triggered_by TEXT NOT NULL DEFAULT 'system',
                reason TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text("CREATE INDEX IF NOT EXISTS idx_commands_machine ON commands(machine_id)")
        )
        await conn.execute(
            sa_text("CREATE INDEX IF NOT EXISTS idx_commands_state ON commands(state)")
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_lifecycle_command ON command_lifecycle(command_id)"
            )
        )

        # Phase 13: Config sync tables
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS configuration_packages (
                id TEXT PRIMARY KEY,
                package_id TEXT NOT NULL UNIQUE,
                package_type TEXT NOT NULL DEFAULT '',
                version TEXT NOT NULL DEFAULT '1',
                format_type TEXT NOT NULL DEFAULT 'full',
                state TEXT NOT NULL DEFAULT 'created',
                checksum TEXT NOT NULL DEFAULT '',
                signature TEXT NOT NULL DEFAULT '',
                payload TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                minimum_agent_version TEXT NOT NULL DEFAULT '',
                rollback_version TEXT NOT NULL DEFAULT '',
                base_package_id TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS machine_package_versions (
                machine_uuid TEXT NOT NULL,
                package_type TEXT NOT NULL,
                current_version TEXT NOT NULL DEFAULT '0',
                desired_version TEXT NOT NULL DEFAULT '',
                last_sync_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (machine_uuid, package_type)
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS package_history (
                id TEXT PRIMARY KEY,
                package_id TEXT NOT NULL,
                to_state TEXT NOT NULL DEFAULT '',
                triggered_by TEXT NOT NULL DEFAULT 'system',
                reason TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_packages_type ON configuration_packages(package_type)"
            )
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_packages_state ON configuration_packages(state)"
            )
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_machine_versions ON machine_package_versions(machine_uuid)"
            )
        )

        # Phase 16: Discord registration tables
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS discord_guilds (
                id TEXT PRIMARY KEY,
                guild_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL DEFAULT '',
                owner_id TEXT NOT NULL DEFAULT '',
                category_id TEXT NOT NULL DEFAULT '',
                registered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                verified INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS discord_guild_settings (
                id TEXT PRIMARY KEY,
                guild_id TEXT NOT NULL UNIQUE,
                category_name TEXT NOT NULL DEFAULT 'AI Security',
                permission_rules TEXT NOT NULL DEFAULT '{}',
                heartbeat_interval_seconds INTEGER NOT NULL DEFAULT 30,
                notification_channel TEXT NOT NULL DEFAULT 'critical-alerts',
                ping_role_id TEXT NOT NULL DEFAULT '',
                maintenance_mode INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS discord_channel_mappings (
                id TEXT PRIMARY KEY,
                guild_id TEXT NOT NULL,
                channel_name TEXT NOT NULL,
                channel_id TEXT NOT NULL DEFAULT '',
                channel_type TEXT NOT NULL DEFAULT 'text',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (guild_id, channel_name)
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS registered_machines (
                id TEXT PRIMARY KEY,
                guild_id TEXT NOT NULL,
                machine_uuid TEXT NOT NULL UNIQUE,
                registered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS notification_preferences (
                id TEXT PRIMARY KEY,
                guild_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                channel_name TEXT NOT NULL DEFAULT 'system-events',
                enabled INTEGER NOT NULL DEFAULT 1,
                ping_role_id TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (guild_id, event_type)
            )
        """)
        )
        await conn.execute(
            sa_text("""
            CREATE TABLE IF NOT EXISTS ping_roles (
                id TEXT PRIMARY KEY,
                guild_id TEXT NOT NULL,
                role_id TEXT NOT NULL,
                event_type TEXT NOT NULL DEFAULT 'critical',
                mention INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_discord_guilds_active ON discord_guilds(guild_id)"
            )
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_discord_mappings_guild ON discord_channel_mappings(guild_id)"
            )
        )
        await conn.execute(
            sa_text(
                "CREATE INDEX IF NOT EXISTS idx_registered_machines_guild ON registered_machines(guild_id)"
            )
        )

    yield engine
    await engine.dispose()


@pytest.fixture
async def sqlite_session(sqlite_engine):
    """Create an async session against the SQLite engine."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(sqlite_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
