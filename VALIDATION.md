# Verification scope — shared session update

Prepared: 2026-10-29.

## Checked locally

- 43 Python tests pass, including two browser-attach calls that must focus the existing video window without navigation, clipboard writes or application launch.
- Checks cover application/window allowlists, reusing open programs, real minimize versus close, maximize/restore, shared mode persistence without deleting the original profile, graceful browser recovery, startup dimensions, authentication-preserving routes, API request/origin validation, payload bounds, safe URL creation, cgroup limits and OOM counters.
- Six portrait/landscape geometry checks pass. All clients use the same shared display size; client zoom does not alter it, fit does not crop it, and enlarged content gets reachable scroll bounds.
- Python, JavaScript and Bash syntax are checked. Docker COPY sources and the flat upload archive are checked.

## Changed behavior

- Opening the browser focuses its current window; it no longer navigates an existing window to Google. The UI does not send a launch or navigation action when a viewer page loads.
- Authenticated clients join one shared X11 desktop. Its default 1280×800 resolution is independent of the viewer's screen. No connect/disconnect application hooks are installed.
- Background timer/renderer throttling flags and disabled virtual display blanking reduce idle interruptions, while the browser remains a normal persistent server process.
- A per-service-run session identifier lets users distinguish reconnecting from restarting the container.
- Normal and safe Brave profiles use fixed server paths. Safe mode is an explicit user action with an independent profile; the original profile is retained.

## Not verified live

Docker and X11 tools are unavailable in the preparation environment. No image build, real program launch/window control, Brave renderer or actual multi-device YouTube playback was run. The live hosted site could not be inspected in the available browser; no live crash diagnosis is claimed.

The desktop actions in automated tests are mocked. Layout checks are calculations rather than screenshots or real touch input. Browser smoke testing and background media behavior need validation after deployment.

## Verify after deployment

1. Keep one replica, the same /config volume, and a service that does not sleep. Open the root HTTPS URL and check login remains required for the UI, /desktop/ and the control API.
2. Open programs on the computer and phone, and test focus, maximize, minimize and restore from the window list.
3. Start a video, note the session ID, close only the outer control tab, then open the same service URL in another browser/device. Verify the same ID, window, page and running playback.
4. Check audio after the new device's first permitted user gesture; receiving audio is separate from keeping server-side media running.
5. Test zoom, the pan/control toggle, fit, full screen, keyboard/text input and desktop mouse controls.
6. If Oops persists, inspect actual memory/OOM indicators and private Brave stderr output, then test the explicit safe-profile recovery. Do not assume all renderer failures are memory-related.
7. Restart/redeploy separately: open processes are expected to close, but profile files and downloads should persist in the mounted volume.

## Operational limits

The update cannot increase a hosting plan's CPU/RAM, prevent the provider from stopping a service, keep processes alive through container restart, or guarantee playback against a site's own behavior. A volume stores files rather than running memory state. Background playback may consume more resources. No fake traffic or network keep-alive loop is added.

Railway's published policy prohibits virtual desktops. Offline technical compatibility does not imply provider permission, availability or guaranteed uptime.
