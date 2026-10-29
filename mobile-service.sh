#!/usr/bin/with-contenv bash
set -euo pipefail
exec s6-setuidgid abc python3 -u /opt/cloud-pc/mobile-control.py

