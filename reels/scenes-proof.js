/* Proof scenes for the Company Brain reel composition.
 * Builders are synchronous; the coordinator owns scene visibility and crossfades.
 */
(function () {
  "use strict";

  const scenes = window.REEL_SCENES = window.REEL_SCENES || {};

  function text(value, fallback) {
    return value === null || value === undefined || value === "" ? fallback : String(value);
  }

  function dataFor(beat) {
    return beat.data && typeof beat.data === "object" ? beat.data : {};
  }

  function timing(beat) {
    const start = Number.isFinite(Number(beat.start)) ? Number(beat.start) : 0;
    const end = Number.isFinite(Number(beat.end)) ? Number(beat.end) : start + 3;
    const span = Math.max(0.25, end - start);
    return { start, span, scale: Math.min(1, span / 2) };
  }

  function entrance(H, beat, tl, target, from, offset, duration, ease, phrase) {
    const clock = timing(beat);
    const length = duration * clock.scale;
    const base = clock.start + offset * clock.scale;
    const cueTime = phrase ? H.cue(beat, phrase, base + length) : base + length;
    const spoken = Number.isFinite(cueTime) ? cueTime - length : base;
    // Retain reading order when the same word is spoken at the beat's beginning.
    const latest = clock.start + clock.span - length - 0.12 * clock.scale;
    const at = Math.min(latest, Math.max(base, spoken));
    H.enter(tl, target, from, at, length, ease);
    return target;
  }

  function shell(parent, beat, kind) {
    const H = window.ReelHelpers;
    if (!H) throw new Error("Proof scenes require window.ReelHelpers");
    const root = H.el("div", "proof-scene proof-" + kind, null, parent);
    root.dataset.layout = beat.layout || "graphic";
    return { H, root, data: dataFor(beat) };
  }

  function image(H, parent, className, source, alt) {
    const img = H.el("img", className, null, parent);
    if (/^https?:\/\//i.test(String(source))) img.crossOrigin = "anonymous";
    img.src = String(source);
    img.alt = alt;
    return img;
  }

  scenes["logo-pop"] = function (parent, beat, tl) {
    const { H, root, data } = shell(parent, beat, "logo-pop");
    const title = text(data.title, "Title needed");
    const mark = H.el("div", "proof-logo-tile", null, root);
    if (data.logo) {
      image(H, mark, "proof-logo-image", data.logo, title);
    } else {
      // A typographic initial is a placeholder, not an invented brand mark.
      H.el("span", "proof-logo-initial", title.trim().slice(0, 1).toUpperCase(), mark);
    }
    const label = data.label ? H.el("div", "proof-kicker", String(data.label), root) : null;
    const heading = H.el("h2", "proof-heading proof-logo-title", title, root);
    const rule = H.el("div", "proof-rule", null, root);
    rule.setAttribute("aria-hidden", "true");

    entrance(H, beat, tl, mark, { scale: 0.78, rotation: -6, opacity: 0 }, 0.12, 0.44, "back.out(1.25)");
    if (label) entrance(H, beat, tl, label, { x: 32, opacity: 0 }, 0.24, 0.28, "power2.out", data.label);
    entrance(H, beat, tl, heading, { y: 38, opacity: 0 }, 0.36, 0.58, "power3.out", title);
    entrance(H, beat, tl, rule, { scaleX: 0 }, 0.54, 0.34, "expo.out");
    return root;
  };

  scenes.receipt = function (parent, beat, tl) {
    const { H, root, data } = shell(parent, beat, "receipt");
    const label = H.el("div", "proof-kicker", text(data.label, "Source"), root);
    const title = H.el("h2", "proof-heading proof-receipt-title", text(data.title, "Source receipt"), root);
    const frame = H.el("div", "proof-receipt-frame", null, root);
    let marker = null;
    if (data.image) {
      image(H, frame, "proof-receipt-image", data.image, text(data.title, "Original source capture"));
      if (data.highlight_y !== null && data.highlight_y !== undefined && Number.isFinite(Number(data.highlight_y))) {
        marker = H.el("div", "proof-receipt-highlight", null, frame);
        marker.style.top = (Math.max(0, Math.min(1, Number(data.highlight_y))) * 100) + "%";
        marker.setAttribute("aria-hidden", "true");
        marker.dataset.layoutIgnore = "true";
      }
    } else {
      const missing = H.el("div", "proof-receipt-missing", "Source capture needed", frame);
      entrance(H, beat, tl, missing, { opacity: 0 }, 0.6, 0.42, "sine.out");
    }

    entrance(H, beat, tl, label, { x: -26, opacity: 0 }, 0.12, 0.26, "power2.out", data.label);
    entrance(H, beat, tl, title, { y: 32, opacity: 0 }, 0.24, 0.48, "power3.out", data.title);
    entrance(H, beat, tl, frame, { y: 48, scale: 0.97, opacity: 0 }, 0.4, 0.58, "expo.out");
    if (marker) entrance(H, beat, tl, marker, { scaleX: 0, opacity: 0 }, 0.85, 0.46, "power2.out", data.title);
    return root;
  };

  scenes.counter = function (parent, beat, tl) {
    const { H, root, data } = shell(parent, beat, "counter");
    const supplied = data.value !== null && data.value !== undefined && data.value !== "";
    const value = supplied ? String(data.value) : "Value needed";
    const label = H.el("h2", "proof-heading proof-counter-label", text(data.label, "Count"), root);
    const panel = H.el("div", "proof-counter-panel", null, root);
    const number = H.el("div", "proof-counter-number", null, panel);
    number.setAttribute("aria-label", value);
    const fontSize = supplied ? Math.max(64, Math.min(208, Math.floor(850 / (Math.max(value.length, 1) * 0.64)))) : 76;
    number.style.fontSize = fontSize + "px";
    const reels = [];

    if (supplied) {
      Array.from(value).forEach(function (character) {
        if (/^[0-9]$/.test(character)) {
          const cell = H.el("span", "proof-counter-cell", null, number);
          cell.setAttribute("aria-hidden", "true");
          // These rows deliberately pass through a one-digit clipping window.
          cell.dataset.layoutAllowOverflow = "true";
          // Off-window rolling digits may sit behind the presenter during a
          // split layout. The visible digit remains inside this clipped cell.
          cell.dataset.layoutAllowOcclusion = "true";
          const strip = H.el("span", "proof-counter-strip", null, cell);
          const finalIndex = 10 + Number(character);
          for (let row = 0; row < 20; row += 1) H.el("span", "proof-counter-digit", String(row % 10), strip);
          // The CSS hero frame shows the exact supplied digit. GSAP travels
          // from digit zero to that frame, and restores it on any reverse seek.
          strip.style.marginTop = (-finalIndex) + "em";
          reels.push({ strip, offset: finalIndex * 100 / 20 });
        } else {
          const literal = H.el("span", "proof-counter-literal", character, number);
          literal.setAttribute("aria-hidden", "true");
        }
      });
    } else {
      number.textContent = value;
      number.classList.add("proof-counter-missing");
    }
    const rule = H.el("div", "proof-rule", null, root);
    rule.setAttribute("aria-hidden", "true");

    entrance(H, beat, tl, label, { x: -30, opacity: 0 }, 0.12, 0.42, "power3.out", data.label);
    entrance(H, beat, tl, panel, { scale: 0.91, opacity: 0 }, 0.28, 0.38, "back.out(1.15)");
    reels.forEach(function (reel, index) {
      entrance(H, beat, tl, reel.strip, { yPercent: reel.offset }, 0.42 + Math.min(index * 0.035, 0.2), 0.84, "power4.out", value);
    });
    entrance(H, beat, tl, rule, { scaleX: 0 }, 0.54, 0.32, "expo.out");
    return root;
  };

  scenes["repo-card"] = function (parent, beat, tl) {
    const { H, root, data } = shell(parent, beat, "repo-card");
    const label = H.el("div", "proof-kicker", "Repository", root);
    const card = H.el("div", "proof-repo-panel", null, root);
    const header = H.el("div", "proof-repo-header", null, card);
    const icon = H.el("span", "proof-repo-icon", "</>", header);
    icon.setAttribute("aria-hidden", "true");
    const name = H.el("h2", "proof-heading proof-repo-name", text(data.name, "Repository name needed"), header);
    const description = H.el("p", "proof-repo-description", text(data.description, "Description not supplied"), card);
    const rule = H.el("div", "proof-repo-rule", null, card);
    rule.setAttribute("aria-hidden", "true");
    const stats = H.el("div", "proof-repo-stats", null, card);
    const hasStars = data.stars !== null && data.stars !== undefined && data.stars !== "";
    const star = H.el("div", "proof-repo-star", null, stats);
    const starGlyph = H.el("span", "proof-repo-star-glyph", "★", star);
    starGlyph.setAttribute("aria-hidden", "true");
    H.el("span", "proof-repo-stat-text", hasStars ? String(data.stars) + " stars" : "Stars not supplied", star);
    const language = data.language ? H.el("div", "proof-repo-language", String(data.language), stats) : null;

    entrance(H, beat, tl, label, { x: 28, opacity: 0 }, 0.12, 0.25, "power2.out");
    entrance(H, beat, tl, card, { y: 40, scale: 0.97, opacity: 0 }, 0.24, 0.58, "power3.out");
    entrance(H, beat, tl, icon, { scale: 0.72, opacity: 0 }, 0.35, 0.36, "back.out(1.2)");
    entrance(H, beat, tl, name, { x: 24, opacity: 0 }, 0.42, 0.44, "expo.out", data.name);
    entrance(H, beat, tl, description, { y: 22, opacity: 0 }, 0.56, 0.42, "sine.out");
    entrance(H, beat, tl, rule, { scaleX: 0 }, 0.72, 0.3, "power2.out");
    entrance(H, beat, tl, star, { y: 18, opacity: 0 }, 0.86, 0.36, "power3.out", hasStars ? String(data.stars) : null);
    if (language) entrance(H, beat, tl, language, { x: 20, opacity: 0 }, 1.02, 0.28, "expo.out", data.language);
    return root;
  };
}());
