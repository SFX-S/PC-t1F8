(function (root) {
  "use strict";
  const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
  function geometry(viewWidth, viewHeight, desktop) {
    // Viewer geometry never changes the shared server's resolution.
    const width = Math.round(clamp(Number(desktop?.width) || 1280, 640, 2560));
    const height = Math.round(clamp(Number(desktop?.height) || 800, 480, 1440));
    return { width, height };
  }
  function layout(viewWidth, viewHeight, size, zoom) {
    const factor = Math.min(viewWidth / size.width, viewHeight / size.height) * clamp(zoom, 1, 2.5);
    const width = size.width * factor, height = size.height * factor;
    return { factor, width, height, left: Math.max(0, (viewWidth - width) / 2), top: Math.max(0, (viewHeight - height) / 2), canvasWidth: Math.max(width, viewWidth), canvasHeight: Math.max(height, viewHeight) };
  }
  const api = { geometry, layout, clamp };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MobileLayout = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
