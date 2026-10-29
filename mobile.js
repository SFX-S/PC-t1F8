(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const frame = $("desktop"), viewport = $("viewport"), surface = $("surface");
  const keyboard = $("keyboard-dialog"), more = $("more-menu");
  const programs = $("programs-dialog");
  let zoom = 1, size, remoteSize = { width: 1280, height: 800 }, currentSession, resizeTimer, toastTimer, typedActive = false, panning = false, drag, queue = Promise.resolve();
  function toast(message) {
    $("toast").textContent = message;
    $("toast").hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { $("toast").hidden = true; }, 5000);
  }
  function arrange(resetGeometry = false) {
    const bounds = viewport.getBoundingClientRect();
    if (bounds.width < 1 || bounds.height < 1) return;
    if (!size || resetGeometry) {
      size = MobileLayout.geometry(bounds.width, bounds.height, remoteSize);
      frame.style.width = size.width + "px";
      frame.style.height = size.height + "px";
    }
    const plan = MobileLayout.layout(bounds.width, bounds.height, size, zoom);
    surface.style.width = plan.canvasWidth + "px";
    surface.style.height = plan.canvasHeight + "px";
    frame.style.left = plan.left + "px";
    frame.style.top = plan.top + "px";
    frame.style.transform = "scale(" + plan.factor + ")";
    $("zoom-label").textContent = zoom === 1 ? "ملاءمة" : Math.round(zoom * 100) + "%";
    $("zoom-out").disabled = zoom <= 1;
    $("zoom-in").disabled = zoom >= 2.5;
  }
  function setZoom(value) {
    const old = zoom;
    zoom = MobileLayout.clamp(value, 1, 2.5);
    const x = viewport.scrollLeft, y = viewport.scrollTop;
    arrange();
    viewport.scrollLeft = (x + viewport.clientWidth / 2) * zoom / old - viewport.clientWidth / 2;
    viewport.scrollTop = (y + viewport.clientHeight / 2) * zoom / old - viewport.clientHeight / 2;
    if (zoom === 1) viewport.scrollTo(0, 0);
    setPanning(zoom > 1);
  }
  function setPanning(enabled) {
    panning = enabled;
    $("pan-layer").hidden = !panning;
    $("pan-label").textContent = panning ? "تحكم" : "تحريك";
    $("pan").setAttribute("aria-pressed", String(panning));
  }
  async function post(data) {
    const response = await fetch("/mobile-control/command", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Cloud-PC-Control": "1" },
      body: JSON.stringify(data), signal: AbortSignal.timeout(16000)
    });
    let result;
    try { result = await response.json(); } catch (_) { throw new Error("خدمة التحكم لم تجهز بعد. انتظر قليلًا ثم جرّب."); }
    if (!response.ok) throw new Error(result.error || "تعذر تنفيذ الأمر.");
    return result;
  }
  function request(data, button) {
    if (button) button.disabled = true;
    const work = queue.then(() => post(data));
    queue = work.catch(() => {});
    return work.catch((error) => { toast(error.name === "TimeoutError" ? "استغرق الأمر وقتًا طويلًا. راجع الذاكرة ثم جرّب مجددًا." : error.message); throw error; })
      .finally(() => { if (button) button.disabled = false; });
  }
  document.querySelectorAll("[data-command]").forEach((button) => {
    button.addEventListener("click", () => {
      if (more.open) more.close();
      request({ action: button.dataset.command }, button).catch(() => {});
    });
  });
  $("navigate").addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = $("address").value.trim();
    if (!text) { $("address").focus(); return; }
    $("address").blur();
    try { await request({ action: "navigate", text }, event.submitter); toast("تم إرسال العنوان إلى Brave."); } catch (_) {}
  });
  $("zoom-in").addEventListener("click", () => setZoom(zoom + .25));
  $("zoom-out").addEventListener("click", () => setZoom(zoom - .25));
  $("fit").addEventListener("click", () => { setZoom(1); arrange(true); });
  $("pan").addEventListener("click", () => setPanning(!panning));
  $("pan-layer").addEventListener("pointerdown", (event) => {
    drag = { x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop };
    event.currentTarget.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  $("pan-layer").addEventListener("pointermove", (event) => {
    if (!drag) return;
    viewport.scrollLeft = drag.left - (event.clientX - drag.x);
    viewport.scrollTop = drag.top - (event.clientY - drag.y);
  });
  $("pan-layer").addEventListener("pointerup", () => { drag = null; });
  $("pan-layer").addEventListener("pointercancel", () => { drag = null; });
  $("fullscreen").addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
      else toast("متصفحك لا يتيح ملء الشاشة هنا. جرّب الوضع الأفقي.");
    } catch (_) { toast("لم يسمح المتصفح بملء الشاشة. جرّب الوضع الأفقي."); }
  });
  $("keyboard").addEventListener("click", () => { typedActive = true; keyboard.showModal(); $("typed-text").focus(); });
  $("keyboard-close").addEventListener("click", () => keyboard.close());
  keyboard.addEventListener("close", () => { typedActive = false; setTimeout(() => arrange(true), 400); });
  $("send-text").addEventListener("click", async (event) => {
    const text = $("typed-text").value;
    if (!text) return;
    try { await request({ action: "paste", text }, event.currentTarget); $("typed-text").value = ""; toast("تم إرسال النص. استخدم Enter عند الحاجة."); } catch (_) {}
  });
  document.querySelectorAll("[data-key]").forEach((button) => {
    button.addEventListener("click", () => request({ action: "key", key: button.dataset.key }, button).catch(() => {}));
  });
  $("more").addEventListener("click", () => more.showModal());
  $("more-close").addEventListener("click", () => more.close());
  $("programs").addEventListener("click", () => { programs.showModal(); refreshStatus(); });
  $("programs-close").addEventListener("click", () => programs.close());
  function programButton(label, data) {
    const button = document.createElement("button");
    button.textContent = label;
    button.addEventListener("click", () => {
      programs.close();
      request(data, button).catch(() => {});
    });
    return button;
  }
  function renderPrograms(status) {
    $("program-list").replaceChildren(programButton("◎ المتصفح الحالي", { action: "open-browser" }));
    for (const app of status.apps || []) {
      $("program-list").appendChild(programButton(app.icon + " " + app.label, { action: "open-program", app: app.id }));
    }
    $("window-list").replaceChildren();
    for (const window of status.windows || []) {
      $("window-list").appendChild(programButton(window.title, { action: "focus-window", window: window.id }));
    }
    if (!(status.windows || []).length) $("window-list").textContent = "لا توجد نوافذ ظاهرة بعد، أو سطح المكتب قيد التشغيل.";
  }
  $("reconnect").addEventListener("click", () => { more.close(); frame.src = "/desktop/?reconnect=" + Date.now(); toast("جارٍ إعادة اتصال الشاشة…"); });
  async function refreshStatus() {
    try {
      const response = await fetch("/mobile-control/status", { credentials: "same-origin", cache: "no-store", signal: AbortSignal.timeout(5000) });
      if (!response.ok) throw new Error();
      const status = await response.json(), memory = status.memory;
      if (status.session) {
        const session = status.session;
        if (currentSession && currentSession !== session.id) {
          toast("أعيد تشغيل الخدمة؛ هذه جلسة تشغيل جديدة. الملفات المحفوظة تبقى في التخزين الدائم.");
          frame.src = "/desktop/";
        }
        currentSession = session.id;
        $("session-label").textContent = "جلسة " + session.id + (session.browser_mode === "safe" ? " · Brave آمن" : " · مشتركة");
        if (session.width !== remoteSize.width || session.height !== remoteSize.height) {
          remoteSize = { width: session.width, height: session.height };
          arrange(true);
        }
      }
      renderPrograms(status);
      $("memory").textContent = memory.used_mb !== null ? "RAM " + memory.used_mb + (memory.limit_mb ? " / " + memory.limit_mb : "") + " MB" : "خدمة التحكم جاهزة";
      const pressure = memory.limit_mb && memory.used_mb / memory.limit_mb > .88;
      $("warning").hidden = !(memory.low_memory || pressure || memory.oom_kills > 0);
      if (memory.oom_kills > 0) $("warning").textContent = "سجّل السيرفر إغلاق برنامج بسبب نفاد الذاكرة. قلل التبويبات أو زد الذاكرة ثم أعد تشغيل Brave من ⋯.";
      else if (!$("warning").hidden) $("warning").textContent = "الذاكرة محدودة: افتح تبويبات قليلة. إذا تعطّل Brave، قلل الحمل أو زد موارد الخدمة.";
    } catch (_) { $("memory").textContent = "التحكم قيد الاتصال…"; }
  }
  function onResize() {
    document.documentElement.style.setProperty("--app-height", Math.round(window.visualViewport ? window.visualViewport.height : window.innerHeight) + "px");
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (!typedActive && document.activeElement !== $("address")) arrange(true);
      else arrange(false);
    }, 350);
  }
  window.addEventListener("resize", onResize);
  if (window.visualViewport) window.visualViewport.addEventListener("resize", onResize);
  document.addEventListener("fullscreenchange", onResize);
  new ResizeObserver(onResize).observe(viewport);
  onResize();
  arrange(true);
  frame.src = "/desktop/";
  refreshStatus();
  setInterval(refreshStatus, 15000);
})();
