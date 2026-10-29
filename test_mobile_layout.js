"use strict";
const assert = require("node:assert/strict");
const { geometry, layout } = require("./mobile-layout.js");
let checked = 0;
for (const [width, height] of [[360, 510], [390, 620], [430, 700], [740, 220], [1024, 640], [1920, 1000]]) {
  const size = geometry(width, height);
  const fit = layout(width, height, size, 1);
  assert(fit.width <= width + .01 && fit.height <= height + .01, "Fit must not crop the screen");
  assert(fit.left >= 0 && fit.top >= 0, "No unreachable negative offsets");
  const bigger = layout(width, height, size, 2);
  assert.equal(bigger.factor, fit.factor * 2, "Visual zoom preserves server resolution");
  assert(bigger.canvasWidth >= bigger.width && bigger.canvasHeight >= bigger.height, "All zoomed content must be scrollable");
  assert(size.width <= 1600 && size.height <= 1280, "Desktop resolution must stay bounded");
  checked++;
}
assert.equal(layout(390, 620, geometry(390, 620), 99).factor, layout(390, 620, geometry(390, 620), 2.5).factor);
assert.deepEqual(geometry(390, 620), geometry(1920, 1000), "New devices must not change the shared desktop size");
assert.deepEqual(geometry(390, 620, {width: 1600, height: 900}), geometry(1920, 1000, {width: 1600, height: 900}));
process.stdout.write("Mobile layout: " + checked + " portrait/landscape sizes passed.\n");
