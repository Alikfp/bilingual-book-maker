#!/bin/bash
# Sync web/ + books/ to Lightsail. Run from project root.
#
# Usage:
#   ./deploy/sync-to-lightsail.sh user@IP path/to/key.pem
#
# Or for one terminal session only (not saved anywhere):
#   export LIGHTSAIL_KEY=./LightsailDefaultKey-ap-southeast-2.pem
#   ./deploy/sync-to-lightsail.sh ubuntu@13.239.132.197

set -euo pipefail

REMOTE="${1:?Usage: $0 user@IP [key.pem]}"
KEY="${2:-${LIGHTSAIL_KEY:-}}"
REMOTE_DIR="/var/www/bilingual-book-maker"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

RSYNC=(rsync -avz)
SSH=(ssh)
if [ -n "$KEY" ]; then
  KEY="${KEY/#\~/$HOME}"
  RSYNC+=(-e "ssh -i $KEY")
  SSH=(ssh -i "$KEY")
fi

# /var/www is root-owned; ubuntu needs write access (safe to re-run)
"${SSH[@]}" "$REMOTE" "sudo mkdir -p '$REMOTE_DIR' && sudo chown -R ubuntu:ubuntu '$REMOTE_DIR'"

echo "Syncing to $REMOTE:$REMOTE_DIR"

"${RSYNC[@]}" "$ROOT/index.html" "$REMOTE:$REMOTE_DIR/"
"${RSYNC[@]}" --delete "$ROOT/web/" "$REMOTE:$REMOTE_DIR/web/"
"${RSYNC[@]}" "$ROOT/books/" "$REMOTE:$REMOTE_DIR/books/"
"${RSYNC[@]}" "$ROOT/deploy/" "$REMOTE:$REMOTE_DIR/deploy/"

echo "Done. Open http://YOUR_IP/web/"
