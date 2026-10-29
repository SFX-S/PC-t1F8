#!/usr/bin/env bash
set -euo pipefail
# Keep the virtual display active. No network pings or artificial keep-alives.
if command -v xset >/dev/null 2>&1; then
  xset s off >/dev/null 2>&1 || true
  xset s noblank >/dev/null 2>&1 || true
  xset -dpms >/dev/null 2>&1 || true
fi
if [[ "${BROWSER_AUTO_START:-false}" == true ]]; then
  exec /usr/local/bin/cloud-brave https://www.google.com/
fi

