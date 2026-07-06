# AI Security Platform — Deployment Guide

## Overview

This guide covers production deployment of the AI Security Platform on Ubuntu 22.04+/Debian 12+.

### Components

| Component | Service Name | Port | Type |
|-----------|-------------|------|------|
| Management Server | `ai-security-management` | 8000 (localhost) | systemd + gunicorn |
| Discord Relay Bot | `ai-security-discord-relay` | — | systemd |
| PostgreSQL | `postgresql` | 5432 | systemd |
| Nginx | `nginx` | 80/443 (public) | systemd |

### Architecture

```
Internet
    │
    ▼
  DNS: api.yourotserver.com → A record → server IP
    │
    ▼
  Nginx (port 443, HTTPS, HTTP/2)
    │  ├── TLS termination (Let's Encrypt)
    │  ├── Security headers (HSTS, CSP, etc.)
    │  ├── Rate limiting
    │  └── WebSocket support
    │
    ▼
  127.0.0.1:8000
    │
    ▼
  Gunicorn + Uvicorn (4 workers)
    │
    ├── FastAPI Management Server
    │       ├── REST API endpoints
    │       ├── Health check (/health)
    │       ├── Pairing protocol
    │       ├── Heartbeat management
    │       └── Notification engine
    │
    └── Discord Relay Bot (separate process)
            ├── Communicates via HTTPS to api.yourotserver.com
            ├── Slash commands → Discord API
            └── Polls Management Server for notifications
```

## Directory Layout

```
/opt/ai-security/
├── management-server/
│   ├── src/management_server/     # Application code
│   ├── migrations/                # SQL migrations (postgres/ + sqlite/)
│   ├── config/                    # YAML policies/routing
│   ├── .venv/                     # Python virtual environment
│   ├── .env                       # Configuration (chmod 600)
│   └── data/                      # SQLite database (dev mode)
│
├── discord-relay/
│   ├── src/                       # Discord Relay Bot v2 code
│   ├── .venv/                     # Python virtual environment
│   ├── .env                       # Configuration (chmod 600)
│   └── .schema_version.json       # Command migration state
│
└── data/                          # Persistent data (future use)

/var/log/ai-security/
├── management/                    # Management Server logs
├── json/                          # JSONL audit logs
├── reports/                       # Generated reports
└── security/ audit/ firewall/ …  # Category logs
```

## Prerequisites

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip nginx certbot python3-certbot-nginx
```

## DNS Configuration

Point `api.yourotserver.com` to your server's public IP address.

```bash
# Verify DNS resolution
dig +short api.yourotserver.com
# Should return: <your-server-public-ip>
```

> **Important:** DNS must resolve before obtaining Let's Encrypt certificates. The certbot HTTP-01 challenge requires port 80 to be reachable from the internet.

## Firewall Configuration

```bash
# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Optional: rate limit SSH
sudo ufw limit ssh

# Enable firewall
sudo ufw enable
```

## Installation

### Quick Install

```bash
# 1. Run the installer
sudo bash /opt/ai-security/management-server/scripts/install-management.sh

# 2. Deploy HTTPS
sudo bash /opt/ai-security/management-server/scripts/deploy-https.sh
```

### Manual Install

```bash
# 1. Create service user
sudo useradd --system --user-group --home-dir /opt/ai-security ai-security

# 2. Set up directories
sudo mkdir -p /opt/ai-security/management-server
sudo mkdir -p /opt/ai-security/discord-relay
sudo chown ai-security:ai-security /opt/ai-security/management-server
sudo chown ai-security:ai-security /opt/ai-security/discord-relay

# 3. Copy source code
sudo cp -r src/ /opt/ai-security/management-server/
sudo cp -r migrations/ /opt/ai-security/management-server/
sudo cp -r config/ /opt/ai-security/management-server/
sudo cp pyproject.toml /opt/ai-security/management-server/

# 4. Set up Python virtual environment
sudo -u ai-security python3 -m venv /opt/ai-security/management-server/.venv
sudo -u ai-security /opt/ai-security/management-server/.venv/bin/pip install -e /opt/ai-security/management-server/

# 5. Configure environment
sudo cp config/.env.example /opt/ai-security/management-server/.env
sudo chmod 600 /opt/ai-security/management-server/.env
# Edit .env with your settings

# 6. Set up systemd services
sudo cp deployment/ai-security-management.service /etc/systemd/system/
sudo cp deployment/ai-security-discord-relay.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-security-management
sudo systemctl start ai-security-management

# 7. Set up Nginx + TLS
sudo bash scripts/deploy-https.sh

# 8. Set up Discord Relay
sudo -u ai-security python3 -m venv /opt/ai-security/discord-relay/.venv
sudo -u ai-security /opt/ai-security/discord-relay/.venv/bin/pip install -r requirements.txt
sudo cp /opt/ai-security/discord-relay/.env.example /opt/ai-security/discord-relay/.env
# Edit .env with DISCORD_TOKEN and DISCORD_API_BASE_URL
sudo systemctl enable ai-security-discord-relay
sudo systemctl start ai-security-discord-relay
```

## TLS (Let's Encrypt)

Certificates are managed by certbot with automatic renewal.

### Manual Setup

```bash
# Obtain certificate (if not done by install script)
sudo certbot --nginx -d api.yourotserver.com \
    --email your-email@example.com \
    --agree-tos --non-interactive

# The nginx config is updated automatically by certbot.
```

### Certificate Information

```bash
# View certificate details
sudo openssl x509 -in /etc/letsencrypt/live/api.yourotserver.com/fullchain.pem -noout -text

# Check expiry date
sudo openssl x509 -in /etc/letsencrypt/live/api.yourotserver.com/fullchain.pem -noout -enddate
```

### Auto-Renewal

Certificates auto-renew via systemd timer. No manual action required.

```bash
# Check renewal timer status
sudo systemctl status certbot.timer

# Manual renewal test
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew
```

### Troubleshooting Renewal

```bash
# Check renewal logs
sudo journalctl -u certbot.service -n 50

# Common issues:
# - Port 80 must be reachable (check firewall)
# - DNS must resolve to this server
# - Check /var/log/letsencrypt/letsencrypt.log
```

## Nginx Configuration

The production nginx configuration includes:

- **HTTP/2** for multiplexed connections
- **HSTS** (max-age=2 years, includeSubDomains, preload)
- **Security headers**: X-Frame-Options, X-Content-Type-Options, CSP, Permissions-Policy, Referrer-Policy
- **WebSocket support** via Upgrade headers
- **Request buffering disabled** for streaming/long-polling
- **Timeouts**: connect=15s, send=300s, read=300s
- **Health check endpoint** with no caching

Configuration files:

| File | Purpose |
|------|---------|
| `deployment/nginx/api.yourotserver.com.http.conf` | HTTP-only bootstrap (for certbot) |
| `deployment/nginx/api.yourotserver.com.ssl.conf` | Production HTTPS config (with certbot managed SSL) |

### Verify Nginx

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Service Management

```bash
# Status
systemctl status ai-security-management
systemctl status ai-security-discord-relay
systemctl status nginx

# Logs
journalctl -u ai-security-management -f
journalctl -u ai-security-discord-relay -f
journalctl -u nginx -f

# Restart
systemctl restart ai-security-management
systemctl restart ai-security-discord-relay
systemctl reload nginx
```

## Health Endpoint

### Usage

```bash
# GET — full health report
curl https://api.yourotserver.com/health

# HEAD — lightweight check (load balancers, monitoring)
curl -I https://api.yourotserver.com/health
```

### Response

```json
{
  "status": "healthy",
  "application": "ai-security-management-server",
  "version": "1.0.0",
  "uptime_seconds": 1234.56,
  "database": {
    "connected": true,
    "migration_version": null,
    "pool_size": 10
  },
  "subsystems": {
    "configuration":  {"state": "healthy"},
    "logging":        {"state": "healthy"},
    "database":       {"state": "healthy"},
    "certificates":   {"state": "healthy"},
    "machines":       {"state": "healthy"},
    "pairing":        {"state": "healthy"},
    "heartbeat":      {"state": "healthy"},
    "policies":       {"state": "healthy"},
    "routing":        {"state": "healthy"},
    "notifications":  {"state": "healthy"},
    "audit":          {"state": "healthy"},
    "commands":       {"state": "healthy"},
    "configsync":     {"state": "healthy"},
    "discord":        {"state": "healthy"}
  },
  "healthy_count": 14,
  "degraded_count": 0,
  "failed_count": 0,
  "startup": { "...": "..." }
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Overall health: `healthy`, `degraded`, or `failed` |
| `application` | string | Application identifier |
| `version` | string | Semantic version from `version.py` (currently `1.0.0`) |
| `uptime_seconds` | float | Seconds since process start (monotonic clock, never negative) |
| `database` | object | Database connection status and pool info |
| `subsystems` | object | Per-subsystem health states (14 subsystems) |
| `healthy_count` | int | Count of healthy subsystems |
| `degraded_count` | int | Count of degraded subsystems |
| `failed_count` | int | Count of failed subsystems |
| `emergency_mode` | object | Emergency mode state (omitted when inactive) |
| `startup` | object | Startup stage results |

### Monitoring Compatibility

| Feature | Status |
|---------|--------|
| GET /health | ✅ HTTP 200 with full JSON body |
| HEAD /health | ✅ HTTP 200, zero content-length |
| HTTP/2 | ✅ Via nginx |
| TLS | ✅ Let's Encrypt |
| Keep-Alive | ✅ Implicit via HTTP/2 |
| Prometheus | ✅ Compatible with blackbox exporter |
| HAProxy health checks | ✅ HEAD support |
| UptimeRobot | ✅ HEAD or GET |
| BetterStack | ✅ GET |

### Version Source

The canonical version string is defined in a single location:

```
src/management_server/version.py  →  VERSION = "1.0.0"
```

All consumers read from this source:
- FastAPI app metadata (`create_app() → app.version`)
- Health endpoint (`/health` → `version` field)
- Version endpoint (`/version` → all fields)
- `get_version_info()` function

## Verifying Discord Relay Bot

```bash
# Check logs
journalctl -u ai-security-discord-relay -n 30

# Expected output:
# Slash commands synced
# Relay Bot v2 connected guilds=N user=YourOTServer-BOT#3504
```

## Security Headers

All API responses include:

| Header | Value |
|--------|-------|
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains; preload` |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` |
| `Permissions-Policy` | All features disabled (API-only) |

## Configuration Reference

### Management Server (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `MGMT_DEBUG` | `false` | Enable debug mode |
| `MGMT_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `MGMT_HOST` | `127.0.0.1` | Bind address (internal only) |
| `MGMT_PORT` | `8000` | Bind port |
| `MGMT_DATABASE_URL` | PostgreSQL | Production database URL |
| `MGMT_DATABASE_URL_OVERRIDE` | — | Override for SQLite dev mode |
| `MGMT_SECRET_KEY` | — | Secret key for signing (auto-generated) |

### Discord Relay (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_TOKEN` | — | Discord bot token (required) |
| `DISCORD_API_BASE_URL` | `https://api.yourotserver.com` | Management Server URL |
| `DISCORD_API_KEY` | — | API key for Management Server |
| `DISCORD_LOG_LEVEL` | `INFO` | Log level |

## Troubleshooting

| Issue | Check |
|-------|-------|
| Service won't start | `journalctl -u ai-security-management -n 50` |
| Database connection failed | PostgreSQL running? Credentials in .env correct? |


## Port Summary

| Port | Service | Bound To | TLS |
|------|---------|----------|-----|
| 443 | Nginx → Management Server | 0.0.0.0 | ✅ Let's Encrypt |
| 80 | Nginx (redirect) | 0.0.0.0 | ❌ (redirects to HTTPS) |
| 8000 | Gunicorn (Management Server) | 127.0.0.1 | ❌ (behind Nginx) |
| 5432 | PostgreSQL | localhost | ❌ (local only) |
