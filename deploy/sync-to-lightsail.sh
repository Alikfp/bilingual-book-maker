#!/bin/bash
# Run on your Mac from the project root.
# Syncs only what the reader needs to your Lightsail instance.
#
# Usage:
#   ./deploy/sync-to-lightsail.sh user@YOUR_STATIC_IP
#
# Example:
#   ./deploy/sync-to-lightsail.sh ubuntu@3.120.45.67

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 user@LIGHTSAIL_IP"
  echo "Example: $0 ubuntu@3.120.45.67"
  exit 1
fi

REMOTE="$1"
REMOTE_DIR="/var/www/bilingual-book-maker"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Syncing from $ROOT to $REMOTE:$REMOTE_DIR"

rsync -avz --delete \
  "$ROOT/index.html" \
  "$ROOT/web/" \
  "$REMOTE:$REMOTE_DIR/web/"

rsync -avz \
  "$ROOT/books/" \
  "$REMOTE:$REMOTE_DIR/books/"

rsync -avz \
  "$ROOT/deploy/" \
  "$REMOTE:$REMOTE_DIR/deploy/"

echo "Done. Open http://YOUR_IP/web/ (or https://your-domain/web/)"
