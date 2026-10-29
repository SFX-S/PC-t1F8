#!/usr/bin/env bash
set -euo pipefail
# Optional check from YOUR machine after the image has been built locally.
# Usage: bash smoke.sh YOUR_RUNNING_CONTAINER_NAME
container="${1:?Pass your running container name}"
docker exec "$container" /usr/bin/brave-browser --version
docker exec --user abc "$container" python3 -c '
from pathlib import Path
p=Path("/config/.cloud-pc-persistence-test")
previous=p.exists()
p.touch(exist_ok=True)
print("Home is writable; previous persistence marker exists:", previous)
'
docker exec "$container" bash -c 'curl --fail --silent --show-error "http://127.0.0.1:${PORT:-8080}/healthz"'
printf '\n'
docker exec "$container" bash -c '
status=$(curl --silent --output /dev/null --write-out "%{http_code}" "http://127.0.0.1:${PORT:-8080}/")
if [[ "$status" != 401 ]]; then
  echo "Expected unauthenticated desktop request to return 401; got $status" >&2
  exit 1
fi
echo "Unauthenticated desktop access is blocked."
'

