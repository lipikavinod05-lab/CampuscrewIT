(function () {
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Count-up numbers: <b data-count="12">
  document.querySelectorAll("[data-count]").forEach(function (el) {
    var target = parseFloat(el.dataset.count) || 0, start = null, dur = 1100;
    if (reduce || target === 0) { el.textContent = target; return; }
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min((ts - start) / dur, 1), eased = 1 - Math.pow(1 - p, 4);
      el.textContent = Math.round(target * eased);
      if (p < 1) requestAnimationFrame(step);
    }
    el.textContent = "0";
    requestAnimationFrame(step);
  });

  // Live countdown: <div data-countdown="2026-11-10T10:00">
  var cd = document.querySelector("[data-countdown]");
  if (cd) {
    var target = new Date(cd.dataset.countdown).getTime();
    var cells = { d: cd.querySelector("[data-u=d]"), h: cd.querySelector("[data-u=h]"), m: cd.querySelector("[data-u=m]") };
    var last = {};
    function tick() {
      var diff = Math.max(0, target - Date.now());
      var vals = { d: Math.floor(diff / 864e5), h: Math.floor(diff / 36e5) % 24, m: Math.floor(diff / 6e4) % 60 };
      Object.keys(vals).forEach(function (k) {
        if (last[k] !== vals[k]) {
          cells[k].textContent = String(vals[k]).padStart(2, "0");
          if (last[k] !== undefined && !reduce) { cells[k].classList.remove("flip"); void cells[k].offsetWidth; cells[k].classList.add("flip"); }
          last[k] = vals[k];
        }
      });
    }
    tick(); setInterval(tick, 15000);
  }

  // Toasts: auto-dismiss + close button
  document.querySelectorAll(".toast").forEach(function (t) {
    function close() { t.classList.add("out"); setTimeout(function () { t.remove(); }, 350); }
    var x = t.querySelector(".x"); if (x) x.addEventListener("click", close);
    setTimeout(close, 5500);
  });

  // Loading state on submit buttons (confirms the click did something)
  document.querySelectorAll("form").forEach(function (f) {
    f.addEventListener("submit", function () {
      var b = f.querySelector("button:not([type=button])");
      if (b) setTimeout(function () { b.classList.add("loading"); }, 0);
    });
  });

  // Auto-submit logo file pickers
  document.querySelectorAll("input[type=file][data-autosubmit]").forEach(function (i) {
    i.addEventListener("change", function () { if (i.files.length) i.form.submit(); });
  });

  // Live table/grid filter: <input data-filter="#id"> filters children matching [data-search]
  document.querySelectorAll("[data-filter]").forEach(function (input) {
    var scope = document.querySelector(input.dataset.filter);
    input.addEventListener("input", function () {
      var q = input.value.trim().toLowerCase();
      scope.querySelectorAll("[data-search]").forEach(function (row) {
        row.hidden = q && row.dataset.search.indexOf(q) === -1;
      });
    });
  });

  // Theme toggle
  var btn = document.getElementById("theme-toggle");
  if (btn) btn.addEventListener("click", function () {
    var root = document.documentElement;
    var dark = root.dataset.theme ? root.dataset.theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("cc-theme", root.dataset.theme); } catch (e) {}
  });
})();
