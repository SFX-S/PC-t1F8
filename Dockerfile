# syntax=docker/dockerfile:1
ARG BASE_IMAGE=lscr.io/linuxserver/webtop:ubuntu-xfce
FROM ${BASE_IMAGE}

USER root
ENV TITLE="Cloud PC - Brave" \
    PUID=1000 PGID=1000 TZ=Asia/Amman \
    START_DOCKER=false PIXELFLUX_WAYLAND=false \
    SELKIES_ENABLE_SHARING=true \
    SELKIES_UI_SIDEBAR_SHOW_SHARING=false \
    SELKIES_FRAMERATE=20 SELKIES_ENABLE_RESIZE=false \
    SELKIES_MANUAL_RESOLUTION=true SELKIES_MANUAL_WIDTH=1280 SELKIES_MANUAL_HEIGHT=800 \
    SELKIES_USE_CSS_SCALING=true SELKIES_SECOND_SCREEN=false \
    SELKIES_AUDIO_ON_START=true SELKIES_WEBCAM_ENABLED=false \
    BROWSER_AUTO_START=false

COPY extra-packages.txt /opt/cloud-pc/extra-packages.txt
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates curl fonts-noto-core fonts-noto-color-emoji git nano python3 wmctrl xdotool xclip \
    && curl --fail --show-error --location --retry 3 \
       https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg \
       -o /usr/share/keyrings/brave-browser-archive-keyring.gpg \
    && curl --fail --show-error --location --retry 3 \
       https://brave-browser-apt-release.s3.brave.com/brave-browser.sources \
       -o /etc/apt/sources.list.d/brave-browser-release.sources \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends brave-browser \
    && python3 -c 'import pathlib,re,subprocess; packages=[s.strip() for line in pathlib.Path("/opt/cloud-pc/extra-packages.txt").read_text().splitlines() if (s:=line.split("#",1)[0]).strip()]; assert all(re.fullmatch(r"[a-z0-9][a-z0-9+.-]*",p) for p in packages), "Use one Ubuntu package name per line"; subprocess.run(["apt-get","install","-y","--no-install-recommends",*packages],check=True) if packages else None' \
    && rm -rf /var/lib/apt/lists/*

COPY cloud-pc-start.sh /usr/local/bin/cloud-pc-start
COPY cloud-brave.sh /usr/local/bin/cloud-brave
COPY init-desktop.sh /custom-cont-init.d/20-cloud-pc
COPY configure-nginx.py /opt/cloud-pc/configure-nginx.py
COPY Brave.desktop /opt/cloud-pc/Brave.desktop
COPY autostart.desktop /opt/cloud-pc/autostart.desktop
COPY brave-helper.desktop /usr/share/xfce4/helpers/brave.desktop
COPY start.html /opt/cloud-pc/start.html
COPY mobile.html /opt/cloud-pc/mobile.html
COPY mobile.js /opt/cloud-pc/mobile.js
COPY mobile-layout.js /opt/cloud-pc/mobile-layout.js
COPY mobile-control.py /opt/cloud-pc/mobile-control.py
COPY mobile-service.sh /custom-services.d/mobile-control
COPY brave-autostart.sh /usr/local/bin/cloud-brave-autostart
RUN chmod 0755 /usr/local/bin/cloud-brave /custom-cont-init.d/20-cloud-pc \
    /usr/local/bin/cloud-pc-start /usr/local/bin/cloud-brave-autostart \
    /custom-services.d/mobile-control \
    && sed -i 's|^Exec=.*|Exec=/usr/local/bin/cloud-brave %U|' /usr/share/applications/brave-browser.desktop \
    && python3 /opt/cloud-pc/configure-nginx.py /defaults/default.conf

EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/cloud-pc-start"]


