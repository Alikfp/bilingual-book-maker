#!/bin/bash
# Run ON the Lightsail instance (as root or with sudo) after first SSH login.
# Installs nginx and places the site config.

set -euo pipefail

SITE_ROOT="/var/www/bilingual-book-maker"
NGINX_SITE="/etc/nginx/sites-available/bilingual-book-maker"

apt-get update
apt-get install -y nginx

mkdir -p "$SITE_ROOT"

# Use bundled config if present, else minimal inline config
if [ -f "$SITE_ROOT/deploy/nginx.conf" ]; then
  cp "$SITE_ROOT/deploy/nginx.conf" "$NGINX_SITE"
else
  cat > "$NGINX_SITE" << 'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    root /var/www/bilingual-book-maker;
    index index.html;
    location / { try_files $uri $uri/ =404; }
}
EOF
fi

ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/bilingual-book-maker
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl enable nginx
systemctl restart nginx

echo "nginx ready. Upload web/ and books/ to $SITE_ROOT from your Mac."
