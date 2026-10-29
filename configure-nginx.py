#!/usr/bin/env python3
"""Add a public web readiness check without changing desktop authentication."""
from pathlib import Path
import sys


def add_health_location(text: str) -> str:
    marker = "  listen 3000 default_server;"
    if text.count(marker) != 1:
        raise ValueError("Upstream Nginx template changed; inspect it before building.")
    block = '''  location = /healthz {
    auth_basic off;
    default_type application/json;
    add_header Cache-Control no-store;
    return 200 '{"status":"web-ready"}';
  }
'''
    return text.replace(marker, block + marker, 1)


def add_mobile_routes(text: str) -> str:
    marker = "  location SUBFOLDER {"
    if text.count(marker) != 2:
        raise ValueError("Expected both HTTP and HTTPS desktop locations in the upstream template.")
    block = '''  location = / {
    alias /opt/cloud-pc/mobile.html;
    default_type text/html;
    add_header Cache-Control "no-store";
    add_header X-Frame-Options SAMEORIGIN;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'self'";
  }
  location = /mobile.js {
    alias /opt/cloud-pc/mobile.js;
    default_type application/javascript;
    add_header Cache-Control "no-store";
  }
  location = /mobile-layout.js {
    alias /opt/cloud-pc/mobile-layout.js;
    default_type application/javascript;
    add_header Cache-Control "no-store";
  }
  location /mobile-control/ {
    proxy_pass http://127.0.0.1:7801/;
    proxy_set_header Host $http_host;
    proxy_set_header Origin $http_origin;
    proxy_set_header X-Cloud-PC-Control $http_x_cloud_pc_control;
    client_max_body_size 32k;
    proxy_connect_timeout 2s;
    proxy_read_timeout 20s;
    proxy_buffering off;
  }
'''
    return text.replace(marker, block + marker)


if __name__ == "__main__":
    path = Path(sys.argv[1])
    path.write_text(add_mobile_routes(add_health_location(path.read_text())))

