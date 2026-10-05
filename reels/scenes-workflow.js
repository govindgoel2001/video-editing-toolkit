/* Seekable workflow explanations. The caller owns scene visibility/transitions. */
(function () {
  "use strict";

  var scenes = window.REEL_SCENES = window.REEL_SCENES || {};
  var NS = "http://www.w3.org/2000/svg";

  function helpers() {
    if (!window.ReelHelpers) throw new Error("Workflow scenes require ReelHelpers.");
    return window.ReelHelpers;
  }

  function text(value, fallback) {
    return value === null || value === undefined || value === "" ? (fallback || "") : String(value);
  }

  function timing(beat) {
    var start = Number(beat.start);
    var end = Number(beat.end);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      throw new RangeError("Workflow beat requires finite start/end and end > start.");
    }
    return { start: start, end: end, span: end - start };
  }

  function at(beat, phrase, fraction) {
    var t = timing(beat);
    var offset = Math.min(0.12, t.span * 0.08);
    var fallback = t.start + Math.max(offset, t.span * fraction);
    var found = Number(helpers().cue(beat, phrase, fallback));
    if (!Number.isFinite(found)) found = fallback;
    return Math.max(t.start + offset, Math.min(found, t.end - Math.min(0.25, t.span * 0.15)));
  }

  function reveal(tl, node, vars, beat, phrase, fraction, duration, ease) {
    var start = at(beat, phrase, fraction);
    var t = timing(beat);
    var available = Math.max(0.001, t.end - start - Math.min(0.1, t.span * 0.04));
    helpers().enter(tl, node, vars, start, Math.min(duration, available, t.span * 0.24), ease);
  }

  function entries(data, key, beat) {
    if (data[key] === undefined || data[key] === null) return [];
    if (!Array.isArray(data[key])) throw new TypeError("Workflow data." + key + " must be an array.");
    var max = beat.layout === "split" ? 4 : 6;
    if (data[key].length > max) {
      throw new RangeError("Workflow " + key + " supports " + max + " entries in " + beat.layout + "; split the supplied facts across beats.");
    }
    return data[key];
  }

  function copy(value, limit, name) {
    var result = text(value);
    if (Array.from(result).length > limit) {
      throw new RangeError("Workflow " + name + " exceeds " + limit + " characters; shorten the copy or split it across beats.");
    }
    return result;
  }

  function shell(parent, beat, tl, title, eyebrow) {
    var h = helpers();
    var wrap = h.el("div", "workflow-shell workflow-shell--" + (beat.layout === "split" ? "split" : "full"), "", parent);
    var head = h.el("div", "workflow-heading", "", wrap);
    var kicker = h.el("div", "workflow-eyebrow", eyebrow, head);
    var heading = h.el("h2", "workflow-title", copy(title, 48, "heading"), head);
    reveal(tl, kicker, { x: -18, opacity: 0 }, beat, eyebrow, 0.035, 0.25, "power4.out");
    reveal(tl, heading, { y: 24, opacity: 0 }, beat, title, 0.055, 0.5, "power3.out");
    return wrap;
  }

  function neutral(parent, beat, tl, label) {
    var node = helpers().el("div", "workflow-empty", label, parent);
    reveal(tl, node, { opacity: 0 }, beat, label, 0.15, 0.4, "sine.out");
    return node;
  }

  function pixelAgent(parent) {
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "workflow-mascot");
    svg.setAttribute("viewBox", "0 0 12 14");
    svg.setAttribute("aria-hidden", "true");
    var pixels = [
      [5, 0, 2, 2, "#ff5c00"], [2, 2, 8, 5, "#111114"],
      [4, 4, 1, 1, "#ffffff"], [7, 4, 1, 1, "#ffffff"],
      [4, 7, 4, 1, "#111114"], [2, 8, 8, 3, "#ff5c00"],
      [0, 8, 2, 2, "#111114"], [10, 8, 2, 2, "#111114"],
      [2, 11, 2, 3, "#111114"], [8, 11, 2, 3, "#111114"]
    ];
    pixels.forEach(function (pixel) {
      var rect = document.createElementNS(NS, "rect");
      ["x", "y", "width", "height"].forEach(function (key, i) { rect.setAttribute(key, pixel[i]); });
      rect.setAttribute("fill", pixel[4]);
      svg.appendChild(rect);
    });
    parent.appendChild(svg);
    return svg;
  }

  scenes.terminal = function (parent, beat, tl) {
    var h = helpers();
    var data = beat.data || {};
    var lines = entries(data, "lines", beat);
    var command = copy(data.command, 90, "command");
    var wrap = shell(parent, beat, tl, "Terminal", "COMMAND");
    var panel = h.el("div", "workflow-terminal", "", wrap);
    var bar = h.el("div", "workflow-terminal-bar", "", panel);
    var dot = h.el("span", "workflow-terminal-dot", "", bar);
    dot.setAttribute("aria-hidden", "true");
    h.el("span", "workflow-terminal-name", "terminal", bar);
    reveal(tl, panel, { scale: 0.97, opacity: 0 }, beat, "terminal", 0.08, 0.45, "expo.out");
    reveal(tl, bar, { x: 14, opacity: 0 }, beat, "command", 0.1, 0.3, "sine.out");

    if (command) {
      var commandRow = h.el("div", "workflow-command", "", panel);
      var prompt = h.el("span", "workflow-prompt", "$", commandRow);
      var code = h.el("code", "workflow-command-copy", "", commandRow);
      reveal(tl, prompt, { opacity: 0 }, beat, command, 0.14, 0.2, "power1.out");
      var chars = Array.from(command);
      var typeStart = at(beat, command, 0.14);
      var t = timing(beat);
      var characterDuration = Math.min(0.04, t.span * 0.05);
      var typeDuration = Math.min(0.9, t.span * 0.22, Math.max(0, t.end - typeStart - characterDuration));
      chars.forEach(function (char, i) {
        var span = h.el("span", "workflow-character", char, code);
        h.enter(tl, span, { opacity: 0 }, typeStart + typeDuration * i / Math.max(1, chars.length - 1), characterDuration, "none");
      });
    }
    var output = h.el("div", "workflow-terminal-output", "", panel);
    lines.forEach(function (line, i) {
      var value = copy(typeof line === "object" && line !== null ? line.text : line, 64, "terminal line");
      var row = h.el("div", "workflow-terminal-line", value, output);
      reveal(tl, row, { x: 15, opacity: 0 }, beat, value, 0.3 + i * 0.035, 0.3, i % 2 ? "power2.out" : "sine.out");
    });
    if (!command && !lines.length) neutral(output, beat, tl, "Command details");
    return wrap;
  };

  scenes.agents = function (parent, beat, tl) {
    var h = helpers();
    var data = beat.data || {};
    var targets = entries(data, "targets", beat);
    var supplied = data.count !== undefined && data.count !== null && data.count !== "";
    var count = supplied ? Number(data.count) : null;
    if (supplied && (!Number.isSafeInteger(count) || count < 0)) throw new RangeError("Workflow agent count must be a non-negative safe integer.");
    var title = copy(data.label || "Agent workflow", 48, "agent label");
    var wrap = shell(parent, beat, tl, title, "WORKFLOW");
    var tray = h.el("div", "workflow-agent-tray", "", wrap);
    var caption = h.el("div", "workflow-agent-count", supplied ? count + (count === 1 ? " agent" : " agents") : "Agents", tray);
    var figures = h.el("div", "workflow-agent-figures", "", tray);
    var visible = supplied ? Math.min(count, 6) : 1;
    for (var i = 0; i < visible; i++) {
      var agent = pixelAgent(figures);
      reveal(tl, agent, { y: 20, scale: 0.82, opacity: 0 }, beat, "agents", 0.16 + i * 0.022, 0.42, "back.out(1.25)");
    }
    reveal(tl, tray, { opacity: 0 }, beat, title, 0.08, 0.4, "sine.out");
    reveal(tl, caption, { x: -18, opacity: 0 }, beat, supplied ? String(count) : "agents", 0.12, 0.3, "power4.out");
    if (targets.length) {
      var rule = h.el("div", "workflow-agent-rule", "", wrap);
      rule.setAttribute("aria-hidden", "true");
      reveal(tl, rule, { scaleX: 0 }, beat, "targets", 0.25, 0.45, "power1.out");
      var list = h.el("div", "workflow-targets", "", wrap);
      targets.forEach(function (target, i) {
        var label = copy(typeof target === "object" && target !== null ? target.label : target, 42, "agent target");
        var card = h.el("div", "workflow-target", "", list);
        var number = h.el("span", "workflow-target-index", String(i + 1).padStart(2, "0"), card);
        h.el("span", "workflow-target-label", label, card);
        reveal(tl, card, { x: i % 2 ? 22 : -22, opacity: 0 }, beat, label, 0.3 + i * 0.035, 0.34, i % 2 ? "expo.out" : "power2.out");
        reveal(tl, number, { scale: 0.8, opacity: 0 }, beat, label, 0.33 + i * 0.035, 0.24, "sine.out");
      });
    }
    return wrap;
  };

  scenes.checklist = function (parent, beat, tl) {
    var h = helpers();
    var data = beat.data || {};
    var items = entries(data, "items", beat);
    var wrap = shell(parent, beat, tl, "Checklist", "REVIEW");
    var panel = h.el("div", "workflow-paper", "", wrap);
    reveal(tl, panel, { scale: 0.97, opacity: 0 }, beat, "checklist", 0.08, 0.4, "expo.out");
    items.forEach(function (item, i) {
      var source = typeof item === "object" && item !== null ? item : { text: item };
      var label = copy(source.text, 60, "checklist item");
      var status = copy(source.status, 18, "checklist status");
      var normalized = status.toLowerCase();
      var symbol = /^(done|pass|passed|complete|completed|yes)$/.test(normalized) ? "✓" : /^(fail|failed|error|no)$/.test(normalized) ? "×" : "·";
      var row = h.el("div", "workflow-check-row", "", panel);
      var mark = h.el("span", "workflow-check-mark" + (symbol !== "·" ? " workflow-check-mark--stated" : ""), symbol, row);
      h.el("span", "workflow-item-text", label, row);
      if (status) h.el("span", "workflow-status", status, row);
      reveal(tl, row, { x: -22, opacity: 0 }, beat, label, 0.16 + i * 0.05, 0.35, i % 2 ? "sine.out" : "power2.out");
      reveal(tl, mark, { scale: 0.6, opacity: 0 }, beat, status || label, 0.2 + i * 0.05, 0.27, "back.out(1.2)");
    });
    if (!items.length) neutral(panel, beat, tl, "Checklist details");
    if (data.verdict !== undefined && data.verdict !== null && data.verdict !== "") {
      var verdict = copy(data.verdict, 60, "verdict");
      var footer = h.el("div", "workflow-verdict", verdict, panel);
      reveal(tl, footer, { y: 12, opacity: 0 }, beat, verdict, 0.47, 0.45, "power4.out");
    }
    return wrap;
  };

  scenes.report = function (parent, beat, tl) {
    var h = helpers();
    var data = beat.data || {};
    var rows = entries(data, "rows", beat);
    var wrap = shell(parent, beat, tl, "Report", "DETAILS");
    var panel = h.el("div", "workflow-paper workflow-report", "", wrap);
    var bar = h.el("div", "workflow-report-bar", "", panel);
    var icon = h.el("span", "workflow-report-icon", "", bar);
    icon.setAttribute("aria-hidden", "true");
    h.el("span", "workflow-report-name", "report", bar);
    // The report frame arrives early; individual facts still use spoken cues.
    reveal(tl, panel, { y: 18, opacity: 0 }, beat, "", 0.08, 0.45, "power3.out");
    reveal(tl, bar, { x: 18, opacity: 0 }, beat, "", 0.12, 0.3, "expo.out");
    rows.forEach(function (row, i) {
      var source = typeof row === "object" && row !== null ? row : { label: row };
      var label = copy(source.label, 48, "report row label");
      var value = copy(source.value, 48, "report row value");
      var line = h.el("div", "workflow-report-row", "", panel);
      h.el("div", "workflow-report-label", label, line);
      if (value) h.el("div", "workflow-report-value", value, line);
      reveal(tl, line, { x: -16, opacity: 0 }, beat, label, 0.18 + i * 0.045, 0.33, i % 2 ? "power2.out" : "sine.out");
    });
    if (!rows.length) neutral(panel, beat, tl, "Report details");
    if (data.diff !== undefined && data.diff !== null && data.diff !== "") {
      var diff = copy(data.diff, 72, "report diff");
      var diffRow = h.el("div", "workflow-report-diff", diff, panel);
      reveal(tl, diffRow, { y: 10, opacity: 0 }, beat, diff, 0.48, 0.42, "power4.out");
    }
    return wrap;
  };

  scenes.scan = function (parent, beat, tl) {
    var h = helpers();
    var data = beat.data || {};
    var issues = entries(data, "issues", beat);
    var label = copy(data.label || "Scan details", 48, "scan label");
    var wrap = shell(parent, beat, tl, label, "SCAN");
    var panel = h.el("div", "workflow-paper workflow-scan", "", wrap);
    var bar = h.el("div", "workflow-scan-bar", "", panel);
    var badge = h.el("span", "workflow-scan-badge", "SCAN", bar);
    var rule = h.el("span", "workflow-scan-rule", "", bar);
    rule.setAttribute("aria-hidden", "true");
    reveal(tl, panel, { scale: 0.96, opacity: 0 }, beat, "scan", 0.08, 0.5, "expo.out");
    reveal(tl, badge, { x: -18, opacity: 0 }, beat, "scan", 0.12, 0.26, "power4.out");
    reveal(tl, rule, { scaleX: 0 }, beat, "scan", 0.15, 0.5, "sine.out");
    issues.forEach(function (issue, i) {
      var value = copy(typeof issue === "object" && issue !== null ? issue.text : issue, 60, "scan issue");
      var row = h.el("div", "workflow-scan-row", "", panel);
      var index = h.el("span", "workflow-scan-index", String(i + 1).padStart(2, "0"), row);
      h.el("span", "workflow-item-text", value, row);
      reveal(tl, row, { y: 16, opacity: 0 }, beat, value, 0.2 + i * 0.047, 0.32, i % 2 ? "power2.out" : "power3.out");
      reveal(tl, index, { scale: 0.7, opacity: 0 }, beat, value, 0.24 + i * 0.047, 0.24, "sine.out");
    });
    if (!issues.length) neutral(panel, beat, tl, "Scan details");
    return wrap;
  };
})();
