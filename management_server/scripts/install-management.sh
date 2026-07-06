#!/usr/bin/env bash
#
# AI Security Management Server — Production Installation
#
# Fully automated. No manual copy steps required.
#
# Usage: sudo bash install-management.sh
#
set -euo pipefail

# ─── Configuration ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="/opt/ai-security"
MGMT_DIR="$REPO_DIR/management-server"
VENV_DIR="$MGMT_DIR/.venv"
SERVICE_USER="ai-security"
SERVICE_GROUP="ai-security"
DOMAIN="api.yourotserver.com"
NGINX_SITE="api.yourotserver.com"
LOG_DIR="/var/log/ai-security"

echo "============================================"
echo " AI Security Management Server — Install"
echo "============================================"
echo "Source: $SCRIPT_DIR"
echo "Target: $MGMT_DIR"

# ─── Prerequisites ──────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "❌ This script must be run as root (sudo)." >&2
    exit 1
fi

echo ""
echo "📦 Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nginx certbot 2>/dev/null || true

# ─── System User ────────────────────────────────────────────────────────────
echo ""
echo "👤 Creating service user..."
id -u $SERVICE_USER &>/dev/null || useradd --system --user-group --home-dir $REPO_DIR --create-home $SERVICE_USER

# ─── Deploy Management Server ───────────────────────────────────────────────
echo ""
echo "📁 Deploying Management Server..."
install -d -o $SERVICE_USER -g $SERVICE_GROUP "$MGMT_DIR"
install -d -o $SERVICE_USER -g $SERVICE_GROUP "$MGMT_DIR/src"
install -d -o $SERVICE_USER -g $SERVICE_GROUP "$MGMT_DIR/config"
install -d -o $SERVICE_USER -g $SERVICE_GROUP "$MGMT_DIR/migrations"

# Copy source code
echo "   Copying application source..."
cp -r "$SCRIPT_DIR/src/management_server" "$MGMT_DIR/src/"
cp -r "$SCRIPT_DIR/config/"* "$MGMT_DIR/config/" 2>/dev/null || true
cp -r "$SCRIPT_DIR/migrations/"* "$MGMT_DIR/migrations/" 2>/dev/null || true

# Copy project files
cp "$SCRIPT_DIR/pyproject.toml" "$MGMT_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR/setup.py" "$MGMT_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR/setup.cfg" "$MGMT_DIR/" 2>/dev/null || true

# ─── Log Directories ────────────────────────────────────────────────────────
echo ""
echo "📁 Creating log directories..."
install -d -o $SERVICE_USER -g $SERVICE_GROUP "$LOG_DIR/management"
install -d -o $SERVICE_USER -g $SERVICE_GROUP "$LOG_DIR/json"
install -d -o $SERVICE_USER -g $SERVICE_GROUP "$LOG_DIR/reports"
install -d -o $SERVICE_USER -g $SERVICE_GROUP "$LOG_DIR/security"
install -d -o $SERVICE_USER -g $SERVICE_GROUP "$LOG_DIR/audit"

# ─── Python Virtual Environment ─────────────────────────────────────────────
echo ""
echo "🐍 Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

echo "   Installing management server dependencies..."
cd "$MGMT_DIR"

# Install the package in development mode (editable)
pip install -q --upgrade pip setuptools wheel
pip install -q -e . 2>/dev/null || {
    # If no setup.py/pyproject, install deps directly
    echo "   (Falling back to direct dependency install)"
    pip install -q fastapi uvicorn[standard] sqlalchemy asyncpg aiosqlite \
        cryptography structlog pydantic-settings aiohttp gunicorn \
        pyyaml python-dateutil httpx
}

# Verify management_server is importable
echo ""
echo "🔍 Verifying package import..."
python -c "
import management_server
print(f'✅ management_server v{getattr(management_server, \"__version__\", \"?\")} imported from {management_server.__file__}')
" || {
    echo "❌ management_server package not importable!"
    echo "   Check: $VENV_DIR/lib/python*/site-packages/"
    echo "   Trying direct path fallback..."
    # Add src/ to path and retry
    PYTHONPATH="$MGMT_DIR/src:$PYTHONPATH" python -c "
import sys
sys.path.insert(0, '$MGMT_DIR/src')
import management_server
print(f'✅ management_server imported from {management_server.__file__}')
" || {
        echo "❌ Cannot import management_server even with direct path!"
        echo "   Check: ls $MGMT_DIR/src/management_server/"
        exit 1
    }
}

deactivate

# ─── Configuration ──────────────────────────────────────────────────────────
echo ""
echo "⚙️  Creating default configuration..."

if [[ ! -f "$MGMT_DIR/.env" ]]; then
    # Detect if PostgreSQL is available
    PG_AVAILABLE=false
    if command -v psql &>/dev/null && pg_isready -q 2>/dev/null; then
        PG_AVAILABLE=true
    fi

    if [[ "$PG_AVAILABLE" == "true" ]]; then
        echo "   PostgreSQL detected — creating production configuration..."
        cat > "$MGMT_DIR/.env" << EOF
MGMT_DEBUG=false
MGMT_LOG_LEVEL=INFO
MGMT_LOG_FORMAT=json
MGMT_HOST=0.0.0.0
MGMT_PORT=8000
MGMT_DATABASE_URL=postgresql+asyncpg://ai_security:CHANGE_ME@localhost:5432/ai_security
MGMT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
EOF
    else
        echo "   PostgreSQL not detected — using SQLite (development mode)..."
        echo "   ⚠️  Set MGMT_DATABASE_URL_OVERRIDE=postgresql+asyncpg://... for production"
        cat > "$MGMT_DIR/.env" << EOF
MGMT_DEBUG=true
MGMT_LOG_LEVEL=DEBUG
MGMT_LOG_FORMAT=json
MGMT_HOST=127.0.0.1
MGMT_PORT=8000
MGMT_DATABASE_URL_OVERRIDE=sqlite+aiosqlite:////opt/ai-security/management-server/data/management.db
MGMT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
EOF
        # Ensure data directory exists
        install -d -o $SERVICE_USER -g $SERVICE_GROUP "$MGMT_DIR/data"
    fi

    chown $SERVICE_USER:$SERVICE_GROUP "$MGMT_DIR/.env"
    chmod 600 "$MGMT_DIR/.env"
    echo "   Created $MGMT_DIR/.env — EDIT THIS FILE"
fi

# ─── Systemd ────────────────────────────────────────────────────────────────
echo ""
echo "⚙️  Installing systemd services..."

cp "$SCRIPT_DIR/deployment/ai-security-management.service" /etc/systemd/system/
systemctl daemon-reload

# ─── Nginx ──────────────────────────────────────────────────────────────────
echo ""
echo "🌐 Installing nginx configuration..."

NGINX_CONF_SRC="$SCRIPT_DIR/deployment/nginx/$NGINX_SITE.http.conf"
if [[ -f "$NGINX_CONF_SRC" ]]; then
    cp "$NGINX_CONF_SRC" /etc/nginx/sites-available/$NGINX_SITE.conf
    ln -sf /etc/nginx/sites-available/$NGINX_SITE.conf /etc/nginx/sites-enabled/
fi
nginx -t && systemctl reload nginx 2>/dev/null || echo "⚠️  Check nginx config: nginx -t"

# ─── Ownership ──────────────────────────────────────────────────────────────
chown -R $SERVICE_USER:$SERVICE_GROUP "$REPO_DIR" 2>/dev/null || true
chown -R $SERVICE_USER:$SERVICE_GROUP "$LOG_DIR" 2>/dev/null || true

# ─── Verify gunicorn can import the app ─────────────────────────────────────
echo ""
echo "🔍 Verifying Gunicorn app import..."
source "$VENV_DIR/bin/activate"
python -c "
from management_server.app import create_app
print('✅ create_app importable from management_server.app')
" || {
    echo "❌ Gunicorn app import failed — aborting."
    deactivate
    exit 1
}
deactivate

# ─── Database ───────────────────────────────────────────────────────────────
if [[ "$PG_AVAILABLE" != "true" ]]; then
    echo ""
    echo "🗄️  SQLite configured (development mode)."
    echo "   To switch to PostgreSQL:"
    echo "   - Install PostgreSQL: apt install postgresql postgresql-client"
    echo "   - Start: systemctl start postgresql"
    echo "   - Create DB: sudo -u postgres createdb ai_security && sudo -u postgres createuser ai_security -P"
    echo "   - Set MGMT_DATABASE_URL_OVERRIDE=postgresql+asyncpg://... in .env"
else
    echo ""
    echo "🗄️  PostgreSQL configured. Ensure the database is ready:"
    echo "   sudo -u postgres createdb ai_security"
    echo "   sudo -u postgres createuser ai_security -P"
fi

# ─── TLS (Let's Encrypt) ────────────────────────────────────────────────────
echo ""
echo "🔐 Obtaining Let's Encrypt TLS certificate..."
if [[ -d "/etc/letsencrypt/live/$DOMAIN" ]]; then
    echo "   Certificate exists, checking renewal..."
    certbot renew --non-interactive 2>/dev/null || true
else
    echo "   No certificate found. Run after DNS is configured:"
    echo "   certbot --nginx -d $DOMAIN"
fi

# ─── Start Services ─────────────────────────────────────────────────────────
echo ""
echo "🚀 Starting services..."

# Reset failed state from previous attempts
systemctl reset-failed ai-security-management.service 2>/dev/null || true

systemctl enable ai-security-management.service || true

# Start management server and poll for health
echo "   Starting Management Server..."
systemctl start ai-security-management.service || {
    echo "❌ Failed to start management server"
    journalctl -u ai-security-management -n 20 --no-pager
    exit 1
}

# Wait for startup
echo "   Waiting for Management Server..."
for i in $(seq 1 15); do
    if curl -sf -k https://$DOMAIN/health > /dev/null 2>&1; then
        echo "✅ Management Server is RUNNING"
        break
    fi
    if [[ $i -eq 15 ]]; then
        echo "❌ Management Server failed to start within 15s"
        journalctl -u ai-security-management -n 30 --no-pager
        exit 1
    fi
    sleep 1
done

# ─── Verification ───────────────────────────────────────────────────────────
echo ""
echo "✅ Verifying deployment..."

# Use a temp Python script to avoid bash quoting issues with f-strings
cat > /tmp/verify_deploy.py << 'PYEOF'
import sys, json
data = json.load(sys.stdin)
print(f'  Status: {data.get("status")}')
print(f'  Version: {data.get("version")}')
stages = data.get("startup", {}).get("stages", {})
for name, info in stages.items():
    print(f'  {name}: {info["state"]}')
PYEOF

curl -s -k https://$DOMAIN/health | python3 /tmp/verify_deploy.py || echo "⚠️  Health check failed"
rm -f /tmp/verify_deploy.py

echo ""
echo "============================================"
echo " Installation complete!"
echo "============================================"
echo ""
echo " Configuration: $MGMT_DIR/.env"
echo " Logs: journalctl -u ai-security-management -f"
echo ""
echo " Next:"
echo "  1. Edit configuration files with your secrets"
echo "  2. Restart: systemctl restart ai-security-management"
echo "  3. Configure TLS: certbot --nginx -d $DOMAIN"
echo "  4. Verify: curl https://$DOMAIN/health"
echo ""
echo " Optional:"
echo "  5. Configure Discord notifications (hosted relay):"
echo "     - Invite the official bot: https://discord.com/oauth2/authorize?client_id=1402414979617001564&permissions=4504115023833280&integration_type=0&scope=bot"
echo "     - Register guild: curl -X POST https://\$DOMAIN/api/v1/discord/register -H \"Content-Type: application/json\" -d '{\"guild_id\": \"YOUR_GUILD_ID\"}'"
echo "     - Run /pair in your Discord server"
echo "     Note: The Discord Relay is a hosted service — no bot hosting required."
echo ""
