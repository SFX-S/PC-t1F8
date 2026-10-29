#!/usr/bin/env bash
set -euo pipefail

export PORT="${PORT:-8080}"
export CUSTOM_USER="${CUSTOM_USER:-admin}"
export CUSTOM_WS_PORT=8082
export CUSTOM_HTTPS_PORT=3001
export SUBFOLDER=/desktop/
export START_DOCKER=false
export DESKTOP_WIDTH="${DESKTOP_WIDTH:-1280}"
export DESKTOP_HEIGHT="${DESKTOP_HEIGHT:-800}"
# All authenticated devices attach to one X11 display. Connecting a phone must
# not resize/recreate the server display or run an application startup hook.
export SELKIES_ENABLE_SHARING=true
export SELKIES_ENABLE_RESIZE='false|locked'
export SELKIES_MANUAL_RESOLUTION='true|locked'
export SELKIES_MANUAL_WIDTH="$DESKTOP_WIDTH"
export SELKIES_MANUAL_HEIGHT="$DESKTOP_HEIGHT"
export SELKIES_RUN_AFTER_CONNECT=""
export SELKIES_RUN_AFTER_DISCONNECT=""

if [[ ! "$DESKTOP_WIDTH" =~ ^[0-9]{3,4}$ || ! "$DESKTOP_HEIGHT" =~ ^[0-9]{3,4}$ ]] || \
   (( 10#$DESKTOP_WIDTH < 640 || 10#$DESKTOP_WIDTH > 2560 || 10#$DESKTOP_HEIGHT < 480 || 10#$DESKTOP_HEIGHT > 1440 )); then
  echo 'ERROR: Desktop size must be 640–2560 wide and 480–1440 high.' >&2
  exit 1
fi

if [[ ! "$PORT" =~ ^[0-9]{4,5}$ ]] || (( 10#$PORT < 1024 || 10#$PORT > 65535 )); then
  echo 'ERROR: PORT must be a number between 1024 and 65535. Use 8080.' >&2
  exit 1
fi
PORT="$((10#$PORT))"
export PORT
export CUSTOM_PORT="$PORT"
case "$PORT" in
  3001|5000|5100|5173|7801|8082)
    echo 'ERROR: PORT conflicts with an internal service. Use 8080.' >&2
    exit 1
    ;;
esac
if [[ ! "$CUSTOM_USER" =~ ^[A-Za-z0-9_-]{1,32}$ ]]; then
  echo 'ERROR: CUSTOM_USER must contain letters, numbers, underscores or hyphens.' >&2
  exit 1
fi
if [[ ! "${PASSWORD:-}" =~ ^[A-Za-z0-9_-]{20,128}$ ]]; then
  echo 'ERROR: Set PASSWORD in service Variables to 20–128 letters, numbers, underscores or hyphens.' >&2
  echo 'Do not put the password in your GitHub files.' >&2
  exit 1
fi
export PASSWORD
if [[ "${1:-}" == "--check-config" ]]; then
  echo "Configuration valid; HTTP port: $PORT; user: $CUSTOM_USER; shared display: ${DESKTOP_WIDTH}x${DESKTOP_HEIGHT}."
  exit 0
fi
if (( EUID != 0 )); then
  echo 'ERROR: This image needs to start as root. Set RAILWAY_RUN_UID=0 if the platform overrides it.' >&2
  exit 1
fi
echo "Starting Cloud PC on 0.0.0.0:$PORT with login required."
echo 'Mount persistent storage at /config to keep your files across deployments.'
install -d -m 0755 /run/cloud-pc
python3 - <<'PY'
from pathlib import Path
import json, os, uuid
from datetime import datetime, timezone
data = {"id": uuid.uuid4().hex[:12], "started_at": datetime.now(timezone.utc).isoformat(),
        "width": int(os.environ["DESKTOP_WIDTH"]), "height": int(os.environ["DESKTOP_HEIGHT"])}
path = Path('/run/cloud-pc/session.json')
path.write_text(json.dumps(data))
path.chmod(0o644)
PY
exec /init "$@"

