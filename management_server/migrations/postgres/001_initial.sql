-- PostgreSQL Migration 001 — All tables
-- This file matches the schema from backend.py for PostgreSQL

CREATE TABLE IF NOT EXISTS migration_history (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    checksum    TEXT NOT NULL DEFAULT '',
    success     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS certificate_authority (
    id              TEXT PRIMARY KEY,
    subject         TEXT NOT NULL,
    key_type        TEXT NOT NULL DEFAULT 'Ed25519',
    certificate_pem TEXT NOT NULL DEFAULT '',
    public_key_pem  TEXT NOT NULL DEFAULT '',
    fingerprint     TEXT NOT NULL DEFAULT '',
    serial          TEXT NOT NULL DEFAULT '',
    not_before      TIMESTAMPTZ,
    not_after       TIMESTAMPTZ,
    is_root         BOOLEAN DEFAULT TRUE,
    is_initialized  BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS machine_certificates (
    id                      TEXT PRIMARY KEY,
    machine_uuid            TEXT NOT NULL UNIQUE,
    serial                  TEXT NOT NULL DEFAULT '',
    subject                 TEXT NOT NULL DEFAULT '',
    issued_at               TIMESTAMPTZ,
    expires_at              TIMESTAMPTZ,
    certificate_pem         TEXT NOT NULL DEFAULT '',
    certificate_fingerprint TEXT NOT NULL DEFAULT '',
    public_key_pem          TEXT NOT NULL DEFAULT '',
    public_key_fingerprint  TEXT NOT NULL DEFAULT '',
    status                  TEXT NOT NULL DEFAULT 'active',
    revoked_at              TIMESTAMPTZ,
    revocation_reason       TEXT NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS machines (
    id                      TEXT PRIMARY KEY,
    machine_uuid            TEXT NOT NULL UNIQUE,
    hostname                TEXT NOT NULL DEFAULT '',
    operating_system        TEXT NOT NULL DEFAULT '',
    architecture            TEXT NOT NULL DEFAULT '',
    environment             TEXT NOT NULL DEFAULT 'production',
    agent_version           TEXT NOT NULL DEFAULT '',
    public_key_fingerprint  TEXT NOT NULL DEFAULT '',
    public_key_pem          TEXT NOT NULL DEFAULT '',
    certificate_fingerprint TEXT NOT NULL DEFAULT '',
    status                  TEXT NOT NULL DEFAULT 'unknown',
    first_seen              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at             TIMESTAMPTZ,
    last_status_change      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS registration_requests (
    id              TEXT PRIMARY KEY,
    machine_uuid    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    public_key_pem  TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pairing_tokens (
    id              TEXT PRIMARY KEY,
    token_id        TEXT NOT NULL UNIQUE,
    token_hash      TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL DEFAULT 'issued',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consumed_at     TIMESTAMPTZ,
    creator         TEXT NOT NULL DEFAULT 'system',
    machine_uuid    TEXT,
    audit_reference TEXT NOT NULL DEFAULT '',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS heartbeats (
    id                  TEXT PRIMARY KEY,
    machine_uuid        TEXT NOT NULL,
    protocol_version    TEXT NOT NULL DEFAULT '1.0',
    agent_version       TEXT NOT NULL DEFAULT '',
    hostname            TEXT NOT NULL DEFAULT '',
    environment         TEXT NOT NULL DEFAULT 'production',
    sequence_number     INTEGER NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'healthy',
    health_json         TEXT NOT NULL DEFAULT '',
    capabilities_json   TEXT NOT NULL DEFAULT '',
    queues_json         TEXT NOT NULL DEFAULT '',
    security_json       TEXT NOT NULL DEFAULT '',
    received_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS machine_status (
    machine_uuid            TEXT PRIMARY KEY,
    status                  TEXT NOT NULL DEFAULT 'unknown',
    last_heartbeat_at       TIMESTAMPTZ,
    protocol_version        TEXT NOT NULL DEFAULT '',
    agent_version           TEXT NOT NULL DEFAULT '',
    hostname                TEXT NOT NULL DEFAULT '',
    environment             TEXT NOT NULL DEFAULT '',
    last_sequence_number    INTEGER NOT NULL DEFAULT 0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS capability_history (
    id              TEXT PRIMARY KEY,
    machine_uuid    TEXT NOT NULL,
    capability      TEXT NOT NULL,
    change_type     TEXT NOT NULL DEFAULT 'changed',
    old_value       TEXT,
    new_value       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS policies (
    name                        TEXT PRIMARY KEY,
    description                 TEXT NOT NULL DEFAULT '',
    version                     TEXT NOT NULL DEFAULT '1',
    parent                      TEXT,
    checksum                    TEXT NOT NULL DEFAULT '',
    heartbeat_interval_seconds  INTEGER NOT NULL DEFAULT 30,
    notification_retention_days INTEGER NOT NULL DEFAULT 30,
    log_retention_days          INTEGER NOT NULL DEFAULT 90,
    ip_masking_enabled          BOOLEAN NOT NULL DEFAULT TRUE,
    maintenance_mode            BOOLEAN NOT NULL DEFAULT FALSE,
    allowed_protocol_versions   TEXT NOT NULL DEFAULT '["1.0"]',
    feature_flags_json          TEXT NOT NULL DEFAULT '{}',
    raw_yaml_json               TEXT NOT NULL DEFAULT '{}',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS machine_policy_assignments (
    id              TEXT PRIMARY KEY,
    machine_uuid    TEXT NOT NULL UNIQUE,
    policy_name     TEXT NOT NULL,
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_by     TEXT NOT NULL DEFAULT 'system'
);

CREATE TABLE IF NOT EXISTS machine_policy_overrides (
    id              TEXT PRIMARY KEY,
    machine_uuid    TEXT NOT NULL,
    policy_name     TEXT NOT NULL DEFAULT '',
    key             TEXT NOT NULL,
    value           TEXT NOT NULL DEFAULT '',
    original_value  TEXT NOT NULL DEFAULT '',
    created_by      TEXT NOT NULL DEFAULT 'admin',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (machine_uuid, key)
);

CREATE TABLE IF NOT EXISTS routing_rules (
    name                TEXT PRIMARY KEY,
    description         TEXT NOT NULL DEFAULT '',
    event_types         TEXT NOT NULL DEFAULT '["*"]',
    destinations        TEXT NOT NULL DEFAULT '["console"]',
    priority            TEXT NOT NULL DEFAULT 'normal',
    template            TEXT NOT NULL DEFAULT 'detailed',
    rate_limit_profile  TEXT NOT NULL DEFAULT 'normal',
    retention_policy    TEXT NOT NULL DEFAULT 'standard',
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS routing_decisions (
    id                  TEXT PRIMARY KEY,
    decision_id         TEXT NOT NULL UNIQUE,
    machine_id          TEXT NOT NULL,
    event_type          TEXT NOT NULL,
    destinations        TEXT NOT NULL DEFAULT '[]',
    priority            TEXT NOT NULL DEFAULT 'normal',
    template            TEXT NOT NULL DEFAULT 'detailed',
    rate_limit_profile  TEXT NOT NULL DEFAULT 'normal',
    retention_policy    TEXT NOT NULL DEFAULT 'standard',
    matched_rule        TEXT NOT NULL DEFAULT '',
    metadata_json       TEXT NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notifications (
    id                  TEXT PRIMARY KEY,
    notification_id     TEXT NOT NULL UNIQUE,
    routing_decision_id TEXT NOT NULL DEFAULT '',
    machine_id          TEXT NOT NULL DEFAULT '',
    event_type          TEXT NOT NULL DEFAULT '',
    destination         TEXT NOT NULL DEFAULT '',
    priority            TEXT NOT NULL DEFAULT 'normal',
    template            TEXT NOT NULL DEFAULT 'detailed',
    payload             TEXT NOT NULL DEFAULT '',
    metadata_json       TEXT NOT NULL DEFAULT '{}',
    status              TEXT NOT NULL DEFAULT 'pending',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS delivery_results (
    id                  TEXT PRIMARY KEY,
    notification_id     TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'success',
    adapter             TEXT NOT NULL DEFAULT '',
    latency_ms          REAL NOT NULL DEFAULT 0.0,
    error_code          TEXT NOT NULL DEFAULT '',
    error_message       TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_events (
    id                  TEXT PRIMARY KEY,
    audit_id            TEXT NOT NULL UNIQUE,
    correlation_id      TEXT NOT NULL DEFAULT '',
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    machine_id          TEXT NOT NULL DEFAULT '',
    subsystem           TEXT NOT NULL DEFAULT '',
    actor               TEXT NOT NULL DEFAULT 'system',
    event_type          TEXT NOT NULL DEFAULT '',
    severity            TEXT NOT NULL DEFAULT 'info',
    outcome             TEXT NOT NULL DEFAULT 'success',
    description         TEXT NOT NULL DEFAULT '',
    metadata_json       TEXT NOT NULL DEFAULT '{}',
    current_hash        TEXT NOT NULL DEFAULT '',
    previous_hash       TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS commands (
    id                  TEXT PRIMARY KEY,
    command_id          TEXT NOT NULL UNIQUE,
    correlation_id      TEXT NOT NULL DEFAULT '',
    machine_id          TEXT NOT NULL DEFAULT '',
    command_type        TEXT NOT NULL DEFAULT '',
    parameters_json     TEXT NOT NULL DEFAULT '{}',
    priority            TEXT NOT NULL DEFAULT 'normal',
    state               TEXT NOT NULL DEFAULT 'created',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    requested_by        TEXT NOT NULL DEFAULT 'system',
    created_at_ts       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS command_lifecycle (
    id              TEXT PRIMARY KEY,
    command_id      TEXT NOT NULL,
    to_state        TEXT NOT NULL DEFAULT '',
    triggered_by    TEXT NOT NULL DEFAULT 'system',
    reason          TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS configuration_packages (
    id                  TEXT PRIMARY KEY,
    package_id          TEXT NOT NULL UNIQUE,
    package_type        TEXT NOT NULL DEFAULT '',
    version             TEXT NOT NULL DEFAULT '1',
    format_type         TEXT NOT NULL DEFAULT 'full',
    state               TEXT NOT NULL DEFAULT 'created',
    checksum            TEXT NOT NULL DEFAULT '',
    signature           TEXT NOT NULL DEFAULT '',
    payload             TEXT NOT NULL DEFAULT '',
    metadata_json       TEXT NOT NULL DEFAULT '{}',
    minimum_agent_version TEXT NOT NULL DEFAULT '',
    rollback_version    TEXT NOT NULL DEFAULT '',
    base_package_id     TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS machine_package_versions (
    machine_uuid    TEXT NOT NULL,
    package_type    TEXT NOT NULL,
    current_version TEXT NOT NULL DEFAULT '0',
    desired_version TEXT NOT NULL DEFAULT '',
    last_sync_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (machine_uuid, package_type)
);

CREATE TABLE IF NOT EXISTS package_history (
    id              TEXT PRIMARY KEY,
    package_id      TEXT NOT NULL,
    to_state        TEXT NOT NULL DEFAULT '',
    triggered_by    TEXT NOT NULL DEFAULT 'system',
    reason          TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS discord_guilds (
    id              TEXT PRIMARY KEY,
    guild_id        TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL DEFAULT '',
    owner_id        TEXT NOT NULL DEFAULT '',
    category_id     TEXT NOT NULL DEFAULT '',
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified        BOOLEAN NOT NULL DEFAULT FALSE,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS discord_guild_settings (
    id                          TEXT PRIMARY KEY,
    guild_id                    TEXT NOT NULL UNIQUE,
    category_name               TEXT NOT NULL DEFAULT 'AI Security',
    permission_rules            TEXT NOT NULL DEFAULT '{}',
    heartbeat_interval_seconds  INTEGER NOT NULL DEFAULT 30,
    notification_channel        TEXT NOT NULL DEFAULT 'critical-alerts',
    ping_role_id                TEXT NOT NULL DEFAULT '',
    maintenance_mode            BOOLEAN NOT NULL DEFAULT FALSE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS discord_channel_mappings (
    id              TEXT PRIMARY KEY,
    guild_id        TEXT NOT NULL,
    channel_name    TEXT NOT NULL,
    channel_id      TEXT NOT NULL DEFAULT '',
    channel_type    TEXT NOT NULL DEFAULT 'text',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (guild_id, channel_name)
);

CREATE TABLE IF NOT EXISTS registered_machines (
    id              TEXT PRIMARY KEY,
    guild_id        TEXT NOT NULL,
    machine_uuid    TEXT NOT NULL UNIQUE,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notification_preferences (
    id              TEXT PRIMARY KEY,
    guild_id        TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    channel_name    TEXT NOT NULL DEFAULT 'system-events',
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    ping_role_id    TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (guild_id, event_type)
);

CREATE TABLE IF NOT EXISTS ping_roles (
    id              TEXT PRIMARY KEY,
    guild_id        TEXT NOT NULL,
    role_id         TEXT NOT NULL,
    event_type      TEXT NOT NULL DEFAULT 'critical',
    mention         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_machines_status ON machines(status);
CREATE INDEX IF NOT EXISTS idx_machines_hostname ON machines(hostname);
CREATE INDEX IF NOT EXISTS idx_registration_machine ON registration_requests(machine_uuid);
CREATE INDEX IF NOT EXISTS idx_pairing_tokens_hash ON pairing_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_pairing_tokens_status ON pairing_tokens(status);
CREATE INDEX IF NOT EXISTS idx_heartbeats_machine ON heartbeats(machine_uuid);
CREATE INDEX IF NOT EXISTS idx_heartbeats_received ON heartbeats(received_at);
CREATE INDEX IF NOT EXISTS idx_capability_machine ON capability_history(machine_uuid);
CREATE INDEX IF NOT EXISTS idx_policy_assignments_machine ON machine_policy_assignments(machine_uuid);
CREATE INDEX IF NOT EXISTS idx_policy_overrides_machine ON machine_policy_overrides(machine_uuid);
CREATE INDEX IF NOT EXISTS idx_routing_decisions_machine ON routing_decisions(machine_id);
CREATE INDEX IF NOT EXISTS idx_routing_decisions_created ON routing_decisions(created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at);
CREATE INDEX IF NOT EXISTS idx_delivery_results_notification ON delivery_results(notification_id);
CREATE INDEX IF NOT EXISTS idx_audit_subsystem ON audit_events(subsystem);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_commands_machine ON commands(machine_id);
CREATE INDEX IF NOT EXISTS idx_commands_state ON commands(state);
CREATE INDEX IF NOT EXISTS idx_lifecycle_command ON command_lifecycle(command_id);
CREATE INDEX IF NOT EXISTS idx_packages_type ON configuration_packages(package_type);
CREATE INDEX IF NOT EXISTS idx_packages_state ON configuration_packages(state);
CREATE INDEX IF NOT EXISTS idx_machine_versions ON machine_package_versions(machine_uuid);
CREATE INDEX IF NOT EXISTS idx_discord_guilds_active ON discord_guilds(guild_id);
CREATE INDEX IF NOT EXISTS idx_discord_mappings_guild ON discord_channel_mappings(guild_id);
CREATE INDEX IF NOT EXISTS idx_registered_machines_guild ON registered_machines(guild_id);

-- Insert initial schema version if empty
INSERT INTO schema_version (version)
SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM schema_version);
