#!/usr/bin/env bash
set -euo pipefail
# The desktop is a container, not a separate VM. Keep Docker's default
# seccomp policy and never grant privileged mode just to launch a browser.
# The Chromium process sandbox is disabled here for container compatibility.
args=(--no-sandbox --test-type --password-store=basic --disable-dev-shm-usage)
args+=(--disable-gpu --no-first-run --no-default-browser-check --disable-session-crashed-bubble)
args+=(--disable-background-mode --renderer-process-limit=2 --window-size=1000,760 --start-maximized)
args+=(--disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding)
# This path belongs to the SERVER, never to a browser, device ID or client URL.
mode=normal
if [[ -f /config/.config/cloud-pc/browser-mode ]]; then
  read -r mode </config/.config/cloud-pc/browser-mode || true
fi
if [[ "$mode" == safe ]]; then
  args+=(--user-data-dir=/config/.config/cloud-pc-brave-safe --disable-extensions --class=CloudPCBraveSafe)
else
  args+=(--user-data-dir=/config/.config/BraveSoftware/Brave-Browser --class=CloudPCBrave)
fi
if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
  args+=(--ozone-platform=wayland)
fi
exec /usr/bin/brave-browser "${args[@]}" "$@"

