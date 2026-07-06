# Installation Guide

## Prerequisites

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip nginx certbot python3-certbot-nginx
```

## DNS Configuration

Point `api.your-server.com` to your server's public IP address.

```bash
# Verify DNS resolution
dig +short api.your-server.com
```

> **Important:** DNS must resolve before obtaining Let's Encrypt certificates. The certbot HTTP-01 challenge requires port 80 to be reachable from the internet.

## Firewall Configuration

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw limit ssh
sudo ufw enable
```

## Quick Install

### Management Server

```bash
# 1. Clone the repository
git clone https://github.com/joelslamospersson/ai-security-agent-rc1.git
cd ai-security-agent-rc1/management_server

# 2. Run the installer (requires root for systemd/nginx setup)
sudo bash scripts/install-management.sh
```

The installer will automatically:
- Create service user and directories
- Set up Python virtual environment
- Install dependencies
- Deploy systemd services
- Configure nginx reverse proxy
- Obtain Let's Encrypt TLS certificate
- Start the Management Server

### HTTPS Deployment

After installation, deploy HTTPS:

```bash
sudo bash /opt/ai-security/management-server/scripts/deploy-https.sh
```

## Manual Installation

### Directory Layout

```
/opt/ai-security/
├── management-server/
│   ├── src/management_server/     # Application code
│   ├── migrations/                # SQL migrations
│   ├── config/                    # YAML policies/routing
│   ├── .venv/                     # Python virtual environment
│   ├── .env                       # Configuration (chmod 600)
│   └── data/                      # SQLite database (dev mode)
├── discord-relay/
│   ├── src/                       # Discord Relay Bot code
│   ├── .venv/                     # Python virtual environment
│   └── .env                       # Configuration (chmod 600)
└── data/                          # Persistent data
```

### Step-by-Step Manual Install

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
sudo cp .env.example /opt/ai-security/management-server/.env
sudo chmod 600 /opt/ai-security/management-server/.env
# Edit .env with your settings

# 6. Set up systemd services
sudo cp deployment/ai-security-management.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-security-management
sudo systemctl start ai-security-management

# 7. Set up Nginx + TLS
sudo bash scripts/deploy-https.sh
```

## Configuration

Copy `.env.example` to `.env` and edit the configuration:

```bash
sudo nano /opt/ai-security/management-server/.env
```

Key configuration variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MGMT_DEBUG` | `false` | Enable debug mode |
| `MGMT_LOG_LEVEL` | `INFO` | Log level |
| `MGMT_HOST` | `127.0.0.1` | Bind address (internal only) |
| `MGMT_PORT` | `8000` | Bind port |
| `MGMT_DATABASE_URL` | PostgreSQL URL | Production database |
| `MGMT_DATABASE_URL_OVERRIDE` | — | Override for SQLite dev mode |
| `MGMT_SECRET_KEY` | — | Secret key |

## Verification

Verify the installation is working:

```bash
# Check service status
systemctl status ai-security-management

# Health check
curl https://api.your-server.com/health

# Expected response:
# {
#   "status": "healthy",
#   "application": "ai-security-management-server",
#   "version": "1.0.0",
#   ...
# }
```

## Pairing

To connect an agent to the Management Server:

1. Generate a pairing token on the server:
   ```bash
   curl -X POST https://api.your-server.com/api/v1/pairing/token \
     -H "Content-Type: application/json" \
     -d '{"machine_name": "my-server-01", "environment": "production"}'
   ```

2. Configure the token on the agent machine in `config.yaml`.

3. Start the agent. It will automatically pair and receive a machine certificate.

## Discord Setup

1. Invite the Discord bot using the invite link.
2. Register your Discord guild with the Management Server.
3. Use the `/pair` slash command to connect.

See the Discord Integration section in the README for details.

## Updating

```bash
# 1. Stop services
sudo systemctl stop ai-security-management

# 2. Pull latest code
cd /opt/ai-security/management-server
git pull

# 3. Install new dependencies
sudo -u ai-security .venv/bin/pip install -e .

# 4. Copy updated source
sudo cp -r src/ /opt/ai-security/management-server/
sudo cp -r migrations/ /opt/ai-security/management-server/

# 5. Start services
sudo systemctl start ai-security-management

# 6. Verify
curl https://api.your-server.com/health
```

## Reinstallation

```bash
# 1. Back up configuration and data
sudo cp /opt/ai-security/management-server/.env ~/mgmt.env.backup

# 2. Run uninstall
# 3. Re-clone and re-install
# 4. Restore configuration
sudo cp ~/mgmt.env.backup /opt/ai-security/management-server/.env

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

## Recovery

In case of failure:

1. Restore database from backup
2. Restore configuration files
3. Restore policy/routing YAML files
4. Start services
5. Verify health endpoint returns healthy
