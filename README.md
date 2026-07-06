# AI Security Agent RC1

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](https://www.python.org/downloads/)

A production-grade, self-hosted security monitoring and response platform. The **AI Security Agent** runs on individual machines, monitoring system logs and detecting threats in real time. The **Management Server** provides centralized policy management, machine registration, secure communication, and incident response.

```
┌─────────────────────┐       ┌──────────────────────────────────┐
│   AI Security Agent │       │       Management Server          │
│   (per machine)     │◄─────►│                                  │
│                     │       │  ┌────────────────────────────┐  │
│  ┌───────────────┐  │       │  │  Policy Engine            │  │
│  │ Journald      │  │       │  │  Detection Rules           │  │
│  │ Monitor       │  │       │  │  Correlation Engine        │  │
│  └───────┬───────┘  │       │  │  Incident Response         │  │
│          ▼          │       │  │  Audit Engine              │  │
│  ┌───────────────┐  │       │  │  Certificate Authority     │  │
│  │ Detection     │  │       │  │  Machine Registry          │  │
│  │ Pipeline      │──┼──────►│  └────────────────────────────┘  │
│  └───────┬───────┘  │       │                                  │
│          ▼          │       │  ┌────────────────────────────┐  │
│  ┌───────────────┐  │       │  │  REST API (FastAPI)        │  │
│  │ Ban Engine    │  │       │  │  HTTPS (nginx)             │  │
│  │ Firewall      │──┼──────►│  │  WebSocket                 │  │
│  └───────────────┘  │       │  └────────────────────────────┘  │
│                     │       │                                  │
│  Threat Intelligence│       │  ┌────────────────────────────┐  │
│  Reputation Engine  │       │  │  PostgreSQL / SQLite       │  │
│  Offline Queue      │       │  │  SHA-256 Audit Chain       │  │
└─────────────────────┘       │  └────────────────────────────┘  │
                              └──────────────────────────────────┘
```

## Features

### AI Security Agent
- **Journald Monitoring** — real-time log analysis via systemd journal
- **Detection Framework** — regex-based and behavioral detection patterns
- **Rule Engine** — YAML-defined rules with 12 comparison operators
- **Correlation Engine** — multi-event attack chain detection (YAML)
- **Threat Scoring** — deterministic risk calculation with weighted factors
- **Reputation Engine** — 10 entity types with time-decaying scores
- **Ban Engine** — 8 escalation levels, 5 configurable policies
- **Firewall Abstraction** — iptables/nftables backend with IP validation
- **Offline Queue** — persists events when Management Server is unreachable
- **SSH Security Pack** — 9 pre-built detectors, 11 YAML rules

### Management Server
- **Certificate Authority** — Ed25519 internal CA with per-machine X.509 certificates
- **Machine Registry** — state machine with approval workflow
- **Secure Pairing** — single-use SHA-256 tokens, 15-minute TTL
- **Heartbeat Protocol** — version negotiation, capability tracking, sequence replay protection
- **Policy Engine** — YAML policies with single inheritance, 6 built-in policies
- **Routing Engine** — fnmatch rule matching, 5 priority levels, 8 destinations
- **Notification Engine** — 5 async priority queues, 4 formatters, extensible adapters
- **Audit Engine** — immutable SHA-256 hash chain, JSON/CSV/Parquet export
- **Remote Command Framework** — 12 typed commands, 4-stage authorization
- **Configuration Sync** — versioned packages with delta support
- **Discord Integration** — optional relay for alerts and management

## Architecture Overview

The platform consists of two main components:

1. **AI Security Agent** — installed on each monitored machine, it reads system logs via journald, applies detection rules and correlation chains, scores threats, and enforces bans through the firewall. The agent operates independently even when disconnected from the Management Server.

2. **Management Server** — the central coordination hub. It manages machine identities via an internal Ed25519 CA, distributes policies, collects heartbeats, routes notifications, and maintains an immutable audit trail. It exposes a REST API (FastAPI) behind an nginx reverse proxy with TLS.

Communication between agent and server is secured with mTLS using per-machine X.509 certificates issued by the internal CA.

## Supported Operating Systems

- **Ubuntu** 22.04 / 24.04 LTS (primary target)
- **Debian** 12+
- **Arch Linux** (community)
- Other Linux distributions with systemd and Python 3.12+

## Requirements

| Component | Minimum |
|-----------|---------|
| Python | 3.12+ |
| RAM | 512 MB (agent), 1 GB (server) |
| Disk | 1 GB (agent), 5 GB (server) |
| Database | PostgreSQL 15+ (production) or SQLite 3.40+ (development) |
| Network | Outbound HTTPS to Management Server (agent) |
| OS | systemd-based Linux distribution |

## Quick Start

### Management Server

```bash
# 1. Clone the repository
git clone https://github.com/joelslamospersson/ai-security-agent-rc1.git
cd ai-security-agent-rc1/management_server

# 2. Run the installer (requires root for systemd/nginx setup)
sudo bash scripts/install-management.sh

# 3. Configure the .env file
sudo nano /opt/ai-security/management-server/.env

# 4. Verify the installation
curl https://api.your-server.com/health
```

### AI Security Agent

```bash
# 1. Install the agent
cd ai-security-agent-rc1
pip install -e .

# 2. Configure
cp config/config.yaml.example config/config.yaml
# Edit config.yaml with your Management Server URL and pairing token

# 3. Start the agent
python -m security_agent --config config/config.yaml
```

## Installation

See [INSTALL.md](INSTALL.md) for detailed installation instructions including Ubuntu setup, dependencies, HTTPS deployment, and verification.

## Configuration

### Management Server

Configuration is via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `MGMT_DEBUG` | `false` | Enable debug mode |
| `MGMT_LOG_LEVEL` | `INFO` | Log level |
| `MGMT_HOST` | `127.0.0.1` | Bind address (internal only) |
| `MGMT_PORT` | `8000` | Bind port |
| `MGMT_DATABASE_URL` | PostgreSQL URL | Production database |
| `MGMT_DATABASE_URL_OVERRIDE` | — | Override for SQLite dev mode |
| `MGMT_SECRET_KEY` | — | Secret key (auto-generated in production) |

### AI Security Agent

Configuration is via `config/config.yaml`. Key settings:

```yaml
general:
  debug: false
  log_level: INFO

management_server:
  url: https://api.your-server.com
  pairing_token: ""  # Generated during pairing

monitoring:
  journald:
    enabled: true
    since: "24h"

detection:
  rules_path: "rules/"
  ssh:
    enabled: true

firewall:
  backend: iptables
  ban_policy: moderate
```

## Pairing

To connect an AI Security Agent to the Management Server:

1. **On the Management Server**, generate a pairing token:
   ```bash
   curl -X POST https://api.your-server.com/api/v1/pairing/token \
     -H "Content-Type: application/json" \
     -d '{"machine_name": "my-server-01", "environment": "production"}'
   ```
   Save the returned token — it is shown only once.

2. **On the agent machine**, configure the token in `config.yaml`:
   ```yaml
   management_server:
     url: https://api.your-server.com
     pairing_token: "pt-xxxxxxxxxxxx"
   ```

3. **Start the agent**. It will automatically present the pairing token, receive a machine certificate (Ed25519, 90-day validity), establish a trusted heartbeat connection, and begin log monitoring and detection.

## Discord Integration

The AI Security Platform can send alerts and notifications through Discord via the official hosted Relay Bot.

### How It Works

1. The Management Server exposes a Discord integration API
2. The official Relay Bot (hosted by the project) connects to your Management Server
3. Alerts, policy violations, and incidents are forwarded to your Discord channels
4. Slash commands allow interactive management

### Setup

1. **Invite the bot** to your Discord server:
   ```
   https://discord.com/oauth2/authorize?client_id=1402414979617001564&permissions=4504115023833280&integration_type=0&scope=bot
   ```

2. **Register the guild** with your Management Server:
   ```bash
   curl -X POST https://api.your-server.com/api/v1/discord/register \
     -H "Content-Type: application/json" \
     -d '{"guild_id": "your-discord-guild-id"}'
   ```

3. **Pair the bot** — run the `/pair` slash command in your Discord server and enter the pairing token from the registration response.

## Updating

### Management Server

```bash
sudo systemctl stop ai-security-management
cd /opt/ai-security/management-server
git pull
sudo -u ai-security .venv/bin/pip install -e .
sudo cp -r src/ /opt/ai-security/management-server/
sudo systemctl start ai-security-management
```

### AI Security Agent

```bash
cd /opt/ai-security/agent
git pull
pip install -e .
sudo systemctl restart ai-security-agent
```

## Reinstallation

### Complete Reinstall

```bash
# 1. Back up configuration and data
sudo cp /opt/ai-security/management-server/.env ~/mgmt.env.backup
sudo cp /opt/ai-security/management-server/data/management.db ~/mgmt.db.backup

# 2. Run uninstall
# 3. Re-clone and install fresh
# 4. Restore configuration from backup
sudo cp ~/mgmt.env.backup /opt/ai-security/management-server/.env
sudo chmod 600 /opt/ai-security/management-server/.env

# 5. Start services
sudo systemctl start ai-security-management
```

## Uninstallation

```bash
# 1. Stop and disable services
sudo systemctl stop ai-security-management
sudo systemctl disable ai-security-management

# 2. Remove systemd service files
sudo rm /etc/systemd/system/ai-security-management.service
sudo systemctl daemon-reload

# 3. Remove nginx configuration
sudo rm /etc/nginx/sites-available/api.your-server.com.conf
sudo rm /etc/nginx/sites-enabled/api.your-server.com.conf
sudo nginx -t && sudo systemctl reload nginx

# 4. Remove application directory
sudo rm -rf /opt/ai-security/management-server

# 5. Remove log files (optional)
sudo rm -rf /var/log/ai-security

# 6. Remove service user (optional)
sudo userdel ai-security
sudo groupdel ai-security

# 7. Drop database (if using PostgreSQL)
sudo -u postgres psql -c "DROP DATABASE ai_security;"
sudo -u postgres psql -c "DROP USER ai_security;"
```

## Troubleshooting

| Issue | Check |
|-------|-------|
| Service won't start | `journalctl -u ai-security-management -n 50` |
| Database connection failed | PostgreSQL running? Credentials correct? |
| Nginx 502 Bad Gateway | Management Server running on 127.0.0.1:8000? |
| TLS cert missing | Run `sudo certbot --nginx -d api.your-server.com` |
| Agent won't pair | Management Server `/health` returns ready? Token not expired? |
| Agent shows "pending approval" | Check management server admin panel to approve |
| Heartbeat failing | Agent can reach `https://api.your-server.com`? Firewall? |

### Health Endpoints

```bash
curl https://api.your-server.com/health      # GET — full status
curl -I https://api.your-server.com/health    # HEAD — lightweight check
curl https://api.your-server.com/version      # Version info
```

## FAQ

**Q: Can I host the Discord Relay Bot myself?**
A: No. The Discord Relay Bot is a hosted service managed by the project. Users only invite the bot to their Discord server. The bot communicates securely with your Management Server.

**Q: Can I use SQLite in production?**
A: SQLite is supported for development and testing. PostgreSQL is recommended for production deployments.

**Q: How do I backup the Management Server?**
A: Back up the `.env` file, the database (SQLite file or PostgreSQL dump), and optionally the CA certificate for emergency recovery.

**Q: What happens if the Management Server is unreachable?**
A: The AI Security Agent continues monitoring and detection locally. Events are queued and synced when connectivity is restored.

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache 2.0. See [LICENSE](LICENSE) for details.
