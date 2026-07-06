#!/usr/bin/env bash
#───────────────────────────────────────────────────────────────────────────────
# deploy-https.sh — Production HTTPS Deployment for AI Security Platform
#───────────────────────────────────────────────────────────────────────────────
# Usage: sudo bash deploy-https.sh
# Requires: nginx, certbot, port 80 reachable from internet
#───────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DOMAIN="api.yourotserver.com"
EMAIL="admin@example.com"

echo "============================================"
echo " AI Security — HTTPS Deployment"
echo "============================================"
echo ""

# ─── Prerequisites ──────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "❌ This script must be run as root (sudo)." >&2
    exit 1
fi

if ! command -v nginx &>/dev/null; then
    echo "❌ nginx is not installed. Install it: apt install nginx" >&2
    exit 1
fi

if ! command -v certbot &>/dev/null; then
    echo "❌ certbot is not installed. Install it: apt install certbot python3-certbot-nginx" >&2
    exit 1
fi

# ─── Step 1: Deploy HTTP-only bootstrap config ──────────────────────────────
echo "📁 Deploying HTTP bootstrap nginx config..."
cp "$PROJECT_DIR/deployment/nginx/api.yourotserver.com.http.conf" \
    /etc/nginx/sites-available/api.yourotserver.com.conf

ln -sf /etc/nginx/sites-available/api.yourotserver.com.conf \
    /etc/nginx/sites-enabled/api.yourotserver.com.conf

# Remove conflicting .conf-less symlink if it exists
rm -f /etc/nginx/sites-enabled/api.yourotserver.com

echo "   Testing nginx configuration..."
nginx -t || { echo "❌ nginx config test failed"; exit 1; }

echo "   Reloading nginx..."
systemctl reload nginx || systemctl restart nginx

# ─── Step 2: Obtain Let's Encrypt certificate ──────────────────────────────
echo ""
echo "🔐 Obtaining Let's Encrypt certificate for $DOMAIN..."

certbot --nginx -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive \
    --redirect \
    --hsts \
    --staple-ocsp \
    --keep-until-expiring

echo "✅ Certificate obtained: /etc/letsencrypt/live/$DOMAIN/fullchain.pem"

# ─── Step 3: Deploy production SSL config ──────────────────────────────────
echo ""
echo "📁 Deploying production SSL nginx config..."
cp "$PROJECT_DIR/deployment/nginx/api.yourotserver.com.ssl.conf" \
    /etc/nginx/sites-available/api.yourotserver.com.conf

nginx -t || { echo "❌ nginx config test failed"; exit 1; }
systemctl reload nginx || systemctl restart nginx

# ─── Step 4: Verify ─────────────────────────────────────────────────────────
echo ""
echo "✅ Verifying HTTPS deployment..."

# Test HTTP redirect
echo "   Testing HTTP→HTTPS redirect..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://$DOMAIN/health" 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" == "301" ]]; then
    echo "   ✅ HTTP → HTTPS redirect (301)"
else
    echo "   ⚠️  HTTP redirect returned $HTTP_CODE (expected 301)"
fi

# Test HTTPS
echo "   Testing HTTPS reachability..."
HTTPS_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://$DOMAIN/health" 2>/dev/null || echo "000")
if [[ "$HTTPS_CODE" == "200" ]]; then
    echo "   ✅ HTTPS → /health → 200"
else
    echo "   ❌ HTTPS health check returned $HTTPS_CODE"
    echo "   Check: systemctl status ai-security-management"
    echo "   Check: journalctl -u ai-security-management -n 30"
fi

# Test security headers
echo "   Testing security headers..."
HSTS=$(curl -skI "https://$DOMAIN/health" 2>/dev/null | grep -i "strict-transport-security" | head -1)
if [[ -n "$HSTS" ]]; then
    echo "   ✅ HSTS header present"
else
    echo "   ⚠️  HSTS header missing"
fi

echo ""
echo "============================================"
echo " HTTPS Deployment Complete!"
echo "============================================"
echo ""
echo "  URL:          https://$DOMAIN"
echo "  Cert:         /etc/letsencrypt/live/$DOMAIN/"
echo "  Expires:      $(openssl x509 -in /etc/letsencrypt/live/$DOMAIN/fullchain.pem -noout -enddate 2>/dev/null | cut -d= -f2)"
echo "  Auto-renew:   systemctl list-timers | grep certbot"
echo ""
echo "  Next steps:"
echo "  1. Configure the AI Security Agent to use https://$DOMAIN"
echo "  2. Test pairing and heartbeat through HTTPS"
echo "  3. Run: curl https://$DOMAIN/health"
echo ""
