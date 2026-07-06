-- 001_initial.sql — Initial schema creation
-- This migration is applied after the base schema from schema.py

-- Indexes for performance (additional to schema.py)
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
CREATE INDEX IF NOT EXISTS idx_rule_matches_created ON rule_matches(created_at);
CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at);
CREATE INDEX IF NOT EXISTS idx_threat_assessments_score ON threat_assessments(threat_score DESC);
CREATE INDEX IF NOT EXISTS idx_reputation_score ON reputation(current_score);
CREATE INDEX IF NOT EXISTS idx_ban_history_created ON ban_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_firewall_ops_created ON firewall_ops(created_at DESC);

-- Application configuration
CREATE TABLE IF NOT EXISTS app_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL DEFAULT '',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO app_config (key, value) VALUES ('schema_version', '1');
INSERT OR IGNORE INTO app_config (key, value) VALUES ('agent_name', 'ai-security-agent');
