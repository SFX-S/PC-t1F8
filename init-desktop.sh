#!/usr/bin/env bash
set -euo pipefail
install -d -o abc -g abc /config/Desktop /config/Downloads /config/.config/autostart
# This hook runs before desktop services start. Locks from a previous container
# hostname must not prevent opening the persistent Brave profile.
for lock in SingletonLock SingletonSocket SingletonCookie; do
  rm -f -- "/config/.config/BraveSoftware/Brave-Browser/$lock"
  rm -f -- "/config/.config/cloud-pc-brave-safe/$lock"
done
if [[ ! -f /config/Desktop/Brave.desktop ]]; then
  install -o abc -g abc -m 0755 /opt/cloud-pc/Brave.desktop /config/Desktop/Brave.desktop
fi
# Replace the project's older autostart entry so an existing volume also gets
# on-demand browser startup. The browser profile itself is left untouched.
install -o abc -g abc -m 0644 /opt/cloud-pc/autostart.desktop /config/.config/autostart/cloud-pc.desktop
if [[ ! -f /config/.config/xfce4/helpers.rc ]]; then
  install -d -o abc -g abc /config/.config/xfce4
  printf '%s\n' 'WebBrowser=brave' >/config/.config/xfce4/helpers.rc
  chown abc:abc /config/.config/xfce4/helpers.rc
fi

