/* Progress rail: fills as you read, highlights the current section, drives the corner chip.
   Written to stay cheap while scrolling on a phone: it measures only when the page width changes (iPhone Safari
   fires a resize every time the address bar slides), moves the fill with a transform, and touches the page
   only when a value actually changed. */
(function () {
  var secs = [].slice.call(document.querySelectorAll("main section[id]"));
  var ticks = [].slice.call(document.querySelectorAll(".rail-tick"));
  var fill = document.getElementById("rail-fill");
  var chip = document.getElementById("chip");
  if (!secs.length || !fill || !chip) return;

  /* The sport icon at the head of the fill (D, 2026-11-05): it follows the fill down the rail, changes with the section (and, in Other Sports, with the sport named by each gold heading)
     and balls turn as you scroll. Everything is optional: with no icon element or no drawings the bar behaves exactly as before. */
  var icon = document.getElementById("rail-icon");
  var railEl = document.querySelector(".rail");
  var ICONS = window.RAIL_ICONS || {}, BY_SECTION = window.RAIL_SECTION_ICON || {}, BY_SPORT = window.RAIL_SPORT_ICON || {};
  var iconMarks = [], railH = 1, lastKey = "", lastTop = -1, lastDeg = -999, lastInnerH = 0;
  var calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var WPM = 230;
  var words = document.querySelector("main").innerText.trim().split(/\s+/).length;
  var tops = [], max = 1, queued = false;
  var lastWidth = window.innerWidth, lastCur = -1, lastText = "", lastScale = -1;

  function measure() {
    max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    tops = secs.map(function (s) {
      return Math.min(max, Math.max(0, s.getBoundingClientRect().top + window.scrollY - 52));
    });
    tops[0] = 0;
    for (var i = 1; i < tops.length; i++) tops[i] = Math.max(tops[i], tops[i - 1]);
    if (icon && railEl) {
      railH = Math.max(1, railEl.getBoundingClientRect().height);
      lastInnerH = window.innerHeight;
      iconMarks = [];
      secs.forEach(function (s) {
        var top = s.getBoundingClientRect().top + window.scrollY;
        var sports = [].slice.call(s.querySelectorAll("h4.sport"));
        var first = sports.length ? BY_SPORT[(sports[0].textContent || "").trim().toLowerCase()] : "";
        iconMarks.push({ y: top, key: first || BY_SECTION[s.id] || "chess" });       // Other Sports opens with its first sport's drawing, not a generic one
        sports.forEach(function (h) {
          var name = (h.textContent || "").trim().toLowerCase();
          iconMarks.push({ y: h.getBoundingClientRect().top + window.scrollY, key: BY_SPORT[name] || "chess" });
        });
      });
      iconMarks.sort(function (a, b) { return a.y - b.y; });
    }
  }

  function moveIcon(y, p) {
    if (!icon || !iconMarks.length) return;
    if (window.innerHeight !== lastInnerH && railEl) {                               // the rail's height follows the window (iPhone Safari's address bar): measure it again so the icon stays on the head of the fill
      railH = Math.max(1, railEl.getBoundingClientRect().height);
      lastInnerH = window.innerHeight;
      lastTop = -1;
    }
    var line = y + window.innerHeight * 0.35, key = iconMarks[0].key;
    for (var m = 0; m < iconMarks.length; m++) if (iconMarks[m].y <= line) key = iconMarks[m].key;
    var d = ICONS[key] || ICONS.chess;
    if (!d) return;
    if (key !== lastKey) {
      icon.innerHTML = '<span class="ri"><svg viewBox="0 0 24 24" aria-hidden="true">' + d.svg + "</svg></span>";
      icon.classList.add("on");
      lastKey = key; lastDeg = -999;
    }
    var top = Math.round(p * railH * 2) / 2;
    if (top !== lastTop) { icon.style.transform = "translate3d(0," + top + "px,0)"; lastTop = top; }
    var deg = calm ? 0 : d.spin ? Math.round((y * 0.6) % 360 / 2) * 2 : Math.round(Math.sin(y / 90) * 7);
    if (deg !== lastDeg) { var ri = icon.firstChild; if (ri) ri.style.transform = "rotate(" + deg + "deg)"; lastDeg = deg; }
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

    var scale = Math.round(p * 1000) / 1000;
    if (scale !== lastScale) { fill.style.transform = "scaleY(" + scale + ")"; lastScale = scale; }
    moveIcon(y, p);

    if (cur !== lastCur) {
      ticks.forEach(function (t, i) {
        t.classList.toggle("done", i <= cur);
        if (i === cur) t.setAttribute("aria-current", "true");
        else t.removeAttribute("aria-current");
      });
      lastCur = cur;
    }

    var read = y / max;
    var pct = Math.round(read * 100);
    var mins = Math.max(1, Math.ceil((words * (1 - read)) / WPM));
    var text = pct >= 100 ? "100% · finished" : pct + "% · " + mins + " min left";
    if (text !== lastText) { chip.textContent = text; lastText = text; }
  }

  function queue() {
    if (!queued) { queued = true; window.requestAnimationFrame(update); }
  }

  window.addEventListener("scroll", queue, { passive: true });
  window.addEventListener("resize", function () {
    if (window.innerWidth !== lastWidth) { lastWidth = window.innerWidth; measure(); queue(); }
  });
  window.addEventListener("load", function () { measure(); queue(); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { measure(); queue(); });
  measure();
  update();
})();
