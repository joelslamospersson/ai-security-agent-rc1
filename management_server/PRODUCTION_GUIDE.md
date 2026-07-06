# Production Guide — AI Security Management Server

## Installation

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- pip / venv

### Setup

```bash
git clone <repo> /opt/ai-security
cd /opt/ai-security/management_server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your settings

# Initialize database
alembic upgrade head

# Start
uvicorn src.management_server.app:create_app --host 0.0.0.0 --port 8000
```

### Discord Adapter (separate process)

```bash
export DISCORD_TOKEN="your_token"
python -m discord_bot.main
```

## Upgrades

1. Backup database and config
2. Pull new version
3. Run migrations: `alembic upgrade head`
4. Restart services

## Directory Structure

```
/var/log/ai-security/
├── security/       — Security events
├── audit/          — Audit events
├── firewall/       — Firewall actions
├── heartbeat/      — Heartbeat logs
├── notifications/  — Notification history
├── commands/       — Command history
├── management/     — Management events
├── performance/    — Performance metrics
├── debug/          — Debug logs
├── json/           — JSONL format (parallel)
└── reports/
    ├── incidents/  — Incident reports
    ├── daily/      — Daily summaries
    ├── weekly/     — Weekly summaries
    └── monthly/    — Monthly summaries
```

## Disaster Recovery

1. Stop all services
2. Restore database from backup
3. Restore configuration files
4. Restore policy/routing YAML files
5. Start services
6. Verify health endpoint returns healthy

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Server won't start | Check database connection, config file, port availability |
| Health endpoint returns degraded | Check database, certificate CA, individual subsystem health |
| Discord not connecting | Check DISCORD_TOKEN, guild permissions, bot intents |
| Logs not writing | Check /var/log/ai-security permissions, disk space |
| Commands not delivering | Check machine registration, certificate validity, heartbeat |
| Notifications not sending | Check routing rules, notification queue, adapter configuration |

### Common Failures

- **Database connection lost**: WAL corruption — run `pg_resetwal` or restore from backup
- **Certificate CA expired**: Regenerate root CA (offline procedure)
- **Disk full**: Retention policy should auto-clean; manually remove old logs from `/var/log/ai-security/`
- **Queue backlog**: Check worker processes; restart if hung

## Backup

Backup the following:

```bash
# Database
pg_dump ai_security > backup_$(date +%Y%m%d).sql

# Configuration
cp .env .env.backup
cp -r config/ config.backup

# Certificates (offline storage critical!)
cp -r certificates/ certificates.backup
```

## Log Locations

| Component | Location |
|-----------|----------|
| Management Server | `/var/log/ai-security/management/` |
| Audit | `/var/log/ai-security/audit/` |
| JSONL (all) | `/var/log/ai-security/json/` |
| Reports | `/var/log/ai-security/reports/` |
| Discord Adapter | stdout/stderr (container logs) |

## Emergency Mode

When critical failures prevent normal operation, activate emergency mode:

```bash
curl -X POST http://localhost:8000/api/v1/emergency/activate \
  -H "Content-Type: application/json" \
  -d '{"reason": "Database corruption"}'
```

In emergency mode:
- Remote commands are disabled
- Configuration publishing is disabled  
- Heartbeat, logging, audit, and notifications continue

## Health Monitoring

The `/health` endpoint provides a comprehensive status overview:

```json
{
  "status": "healthy",
  "subsystems": {
    "database": {"state": "healthy", "message": "Connected"},
    "certificates": {"state": "healthy", "message": ""},
    "logging": {"state": "healthy", "message": ""}
  },
  "overall_health": "healthy",
  "emergency_mode": {"active": false}
}
```
