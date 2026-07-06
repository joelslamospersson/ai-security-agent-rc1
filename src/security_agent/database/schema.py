"""SQL schema definitions for the AI Security Agent database."""

SCHEMA_VERSION = 1


INITIAL_SCHEMA = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
    checksum    TEXT NOT NULL DEFAULT ''
);

-- Events
CREATE TABLE IF NOT EXISTS events (
    event_id        TEXT PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    hostname        TEXT NOT NULL DEFAULT '',
    source          TEXT NOT NULL DEFAULT '',
    source_type     TEXT NOT NULL DEFAULT '',
    event_type      INTEGER NOT NULL DEFAULT 0,
    category        INTEGER NOT NULL DEFAULT 0,
    severity        INTEGER NOT NULL DEFAULT 0,
    source_ip       TEXT,
    raw_message     TEXT NOT NULL DEFAULT '',
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_source_ip ON events(source_ip);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);

-- Rule matches (from rule engine)
CREATE TABLE IF NOT EXISTS rule_matches (
    match_id        TEXT PRIMARY KEY,
    rule_id         TEXT NOT NULL,
    rule_name       TEXT NOT NULL DEFAULT '',
    event_id        TEXT NOT NULL DEFAULT '',
    confidence      INTEGER NOT NULL DEFAULT 0,
    severity        INTEGER NOT NULL DEFAULT 0,
    threat_score    INTEGER NOT NULL DEFAULT 0,
    evidence        TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rule_matches_rule_id ON rule_matches(rule_id);
CREATE INDEX IF NOT EXISTS idx_rule_matches_event_id ON rule_matches(event_id);

-- Security incidents (from correlation engine)
CREATE TABLE IF NOT EXISTS incidents (
    incident_id     TEXT PRIMARY KEY,
    attack_chain_id TEXT NOT NULL DEFAULT '',
    state           TEXT NOT NULL DEFAULT 'active',
    matched_rules   TEXT NOT NULL DEFAULT '[]',
    matched_events  TEXT NOT NULL DEFAULT '[]',
    progress        INTEGER NOT NULL DEFAULT 0,
    evidence        TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_incidents_state ON incidents(state);

-- Threat assessments (from threat engine)
CREATE TABLE IF NOT EXISTS threat_assessments (
    threat_id        TEXT PRIMARY KEY,
    incident_id      TEXT NOT NULL DEFAULT '',
    confidence       INTEGER NOT NULL DEFAULT 0,
    threat_score     INTEGER NOT NULL DEFAULT 0,
    severity         INTEGER NOT NULL DEFAULT 0,
    risk_level       INTEGER NOT NULL DEFAULT 0,
    recommended_action INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_threat_assessments_incident ON threat_assessments(incident_id);

-- Reputation records
CREATE TABLE IF NOT EXISTS reputation (
    entity_type     TEXT NOT NULL,
    entity_value    TEXT NOT NULL,
    current_score   INTEGER NOT NULL DEFAULT 0,
    confidence      INTEGER NOT NULL DEFAULT 0,
    first_seen      TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen       TEXT NOT NULL DEFAULT (datetime('now')),
    event_count     INTEGER NOT NULL DEFAULT 0,
    ban_count       INTEGER NOT NULL DEFAULT 0,
    decay_state     TEXT NOT NULL DEFAULT 'active',
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (entity_type, entity_value)
);

-- Ban history
CREATE TABLE IF NOT EXISTS ban_history (
    ban_id          TEXT PRIMARY KEY,
    entity          TEXT NOT NULL,
    entity_type     TEXT NOT NULL DEFAULT 'ipv4',
    action          TEXT NOT NULL DEFAULT 'temporary_ban',
    ban_level       INTEGER NOT NULL DEFAULT 0,
    duration        INTEGER NOT NULL DEFAULT 0,
    reason          TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ban_history_entity ON ban_history(entity, entity_type);

-- Firewall operations
CREATE TABLE IF NOT EXISTS firewall_ops (
    operation_id    TEXT PRIMARY KEY,
    entity          TEXT NOT NULL,
    entity_type     TEXT NOT NULL DEFAULT 'ipv4',
    operation_type  TEXT NOT NULL DEFAULT 'ban',
    duration        INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'pending',
    reason          TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_firewall_ops_entity ON firewall_ops(entity, entity_type);
CREATE INDEX IF NOT EXISTS idx_firewall_ops_status ON firewall_ops(status);

-- Migration history
CREATE TABLE IF NOT EXISTS migration_history (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
    checksum    TEXT NOT NULL DEFAULT '',
    success     INTEGER NOT NULL DEFAULT 1
);
"""
