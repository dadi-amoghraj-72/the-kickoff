/* Progress rail: fills as you read, highlights the current section, drives the corner chip. */
(function () {
  var secs = [].slice.call(document.querySelectorAll("main section[id]"));
  var ticks = [].slice.call(document.querySelectorAll(".rail-tick"));
  var fill = document.getElementById("rail-fill");
  var chip = document.getElementById("chip");
  if (!secs.length || !fill || !chip) return;

  var WPM = 230;
  var words = document.querySelector("main").innerText.trim().split(/\s+/).length;
  var tops = [], max = 1, queued = false;

  function measure() {
    max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    tops = secs.map(function (s) {
      return Math.min(max, Math.max(0, s.getBoundingClientRect().top + window.scrollY - 52));
    });
    tops[0] = 0;
    for (var i = 1; i < tops.length; i++) tops[i] = Math.max(tops[i], tops[i - 1]);
  }

  function update() {
    queued = false;
    var n = secs.length;
    var y = Math.min(max, Math.max(0, window.scrollY));
    var cur = 0;
    for (var k = 0; k < n; k++) if (tops[k] <= y + 1) cur = k;
    var end = cur + 1 < n ? tops[cur + 1] : max;
    var span = end - tops[cur];
    var frac = span > 0 ? Math.min(1, (y - tops[cur]) / span) : 0;
    var p = y >= max - 1 ? 1 : (cur + frac) / n;
    fill.style.height = (p * 100).toFixed(2) + "%";
    ticks.forEach(function (t, i) {
      t.classList.toggle("done", i <= cur);
      if (i === cur) t.setAttribute("aria-current", "true");
      else t.removeAttribute("aria-current");
    });
    var read = y / max;
    var pct = Math.round(read * 100);
    var mins = Math.ceil((words * (1 - read)) / WPM);
    chip.textContent = pct >= 100 ? "100% · finished" : pct + "% · " + Math.max(1, mins) + " min left";
  }

  function queue() {
    if (!queued) { queued = true; window.requestAnimationFrame(update); }
  }

  window.addEventListener("scroll", queue, { passive: true });
  window.addEventListener("resize", function () { measure(); queue(); });
  window.addEventListener("load", function () { measure(); queue(); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { measure(); queue(); });
  measure();
  update();
})();
