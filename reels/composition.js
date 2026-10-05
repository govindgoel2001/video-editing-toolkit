(function () {
  "use strict";

  const job = window.REEL;
  const root = document.querySelector('[data-composition-id="main"]');
  if (!job || !root || !window.gsap) {
    throw new Error("The reel composition requires job.js, a main composition, and GSAP.");
  }

  const WIDTH = 1080;
  const HEIGHT = 1920;
  const TRANSITION = 0.12;
  const duration = Number(job.duration);
  if (!(duration > 0)) throw new Error("Reel duration must be positive.");

  function finite(value, fallback) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function el(tag, className, text, parent) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (parent) parent.appendChild(node);
    return node;
  }

  // The CSS is the landing state. Do not add an opacity entrance to a digit
  // strip or other target whose caller intentionally animates only its position.
  function enter(tl, target, fromVars, time, length, ease) {
    return tl.from(target, Object.assign({}, fromVars, {
      duration: finite(length, 0.36),
      ease: ease || "power3.out",
      immediateRender: true,
    }), Math.max(0, finite(time, 0.12)));
  }

  function tokens(text) {
    return String(text || "").toLocaleLowerCase("en-US")
      .match(/[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu) || [];
  }

  function cue(beat, phrase, fallbackTime) {
    const sought = tokens(phrase);
    const words = Array.isArray(beat.words) ? beat.words : [];
    const flattened = [];
    words.forEach(function (word) {
      tokens(word.text === undefined ? word.word : word.text).forEach(function (token) {
        flattened.push({ token: token, start: finite(word.start, beat.start) });
      });
    });
    if (sought.length) {
      for (let i = 0; i <= flattened.length - sought.length; i += 1) {
        if (sought.every(function (token, k) { return flattened[i + k].token === token; })) {
          const at = flattened[i].start;
          if (at >= beat.start - 0.001 && at < beat.end) return at;
        }
      }
    }
    return Math.max(beat.start, Math.min(beat.end - 0.04,
      finite(fallbackTime, beat.start + 0.14)));
  }

  window.ReelHelpers = { el: el, enter: enter, cue: cue };
  window.REEL_SCENES = window.REEL_SCENES || {};

  // A page recording is evidence, not a generated stand-in. The media element
  // is timed; its viewport and scene ancestors deliberately are not timed.
  window.REEL_SCENES["page-scroll"] = function (parent, beat, tl) {
    const data = beat.data || {};
    const pace = Math.min(1, Math.max(0.01, (beat.end - beat.start) / 1.8));
    const at = function (offset) { return beat.start + offset * pace; };
    const shell = el("div", "page-scroll-shell", null, parent);
    const label = el("div", "eyebrow page-scroll-label", "SOURCE RECORDING", shell);
    const title = el("h2", "scene-title page-scroll-title",
      data.video ? (data.title || "Source recording") : "Source capture needed", shell);
    const source = el("div", "source-label page-scroll-source",
      data.source_label || data.sourceLabel || data.url || "", shell);
    const viewport = el("div", "page-scroll-viewport", null, shell);

    if (data.video) {
      const video = document.getElementById("page-video-" + beat.index);
      if (!video) throw new Error("Page recordings must be declared in the composition HTML.");
      video.className = "clip page-scroll-video";
      viewport.appendChild(video);
      video.setAttribute("src", String(data.video));
      video.setAttribute("data-start", String(beat.start));
      video.setAttribute("data-duration", String(beat.end - beat.start));
      video.setAttribute("data-track-index", String(beat.index + 10));
      video.setAttribute("data-media-start", String(Math.max(0, finite(data.from, 0))));
      video.setAttribute("data-volume", "0");
      video.setAttribute("muted", "");
      video.setAttribute("playsinline", "");
      video.muted = true;
    } else {
      viewport.classList.add("page-scroll-missing");
      el("p", "scene-copy", "Add a real page recording to this beat.", viewport);
    }

    enter(tl, label, { opacity: 0, x: -20 }, at(0.10), 0.20 * pace, "power3.out");
    enter(tl, title, { opacity: 0, y: 18 }, at(0.14), 0.30 * pace, "expo.out");
    if (source.textContent) {
      enter(tl, source, { opacity: 0, x: 16 }, at(0.19), 0.24 * pace, "sine.out");
    }
    enter(tl, viewport, { opacity: 0, scale: 0.985, y: 12 },
      at(0.20), 0.34 * pace, "circ.out");
  };

  const beats = (job.beats || []).map(function (beat, index) {
    return Object.assign({}, beat, {
      index: finite(beat.index, index),
      start: finite(beat.start, 0),
      end: finite(beat.end, duration),
    });
  }).sort(function (a, b) { return a.start - b.start; });
  if (!beats.length) throw new Error("A reel needs at least one timed beat.");

  const graphics = document.getElementById("graphics");
  const presenterWindow = document.getElementById("presenter-window");
  const presenter = document.getElementById("presenter");
  const cutoutWindow = document.getElementById("cutout-window");
  const cutout = document.getElementById("cutout");
  const captions = document.getElementById("captions");
  if (!graphics || !presenterWindow || !presenter || !captions) {
    throw new Error("The reel is missing graphics, presenter, or captions markup.");
  }
  const hasCutout = Boolean(cutoutWindow && cutout);
  const split = Object.assign({
    card_top: 1250, video_top: 534, band_top: 800, overlap: 10,
  }, job.split || {});
  split.card_top = finite(split.card_top, 1250);
  split.video_top = finite(split.video_top, 534);
  split.band_top = finite(split.band_top, 800);
  split.overlap = finite(split.overlap, 10);

  presenter.muted = true;
  presenter.setAttribute("muted", "");
  presenter.setAttribute("playsinline", "");
  presenterWindow.setAttribute("data-layout-allow-overflow", "");
  if (hasCutout) {
    cutout.muted = true;
    cutout.setAttribute("muted", "");
    cutout.setAttribute("playsinline", "");
    cutout.setAttribute("data-layout-allow-overlap", "");
    cutoutWindow.setAttribute("data-layout-allow-overflow", "");
  }

  const tl = gsap.timeline({ paused: true });

  function geometry(layout) {
    if (layout === "split") {
      const videoTop = hasCutout ? split.video_top : finite(split.simple_video_top, split.video_top);
      return {
        window: { top: split.card_top, left: 0, width: WIDTH,
          height: HEIGHT - split.card_top, borderRadius: "84px 84px 0px 0px",
          boxShadow: "0 -18px 60px rgba(17,17,20,0.18)" },
        video: { top: videoTop - split.card_top },
        cutoutWindow: { top: split.band_top, left: 0, width: WIDTH,
          height: Math.max(0, split.card_top + split.overlap - split.band_top) },
        cutout: { top: split.video_top - split.band_top },
      };
    }
    return {
      window: { top: 0, left: 0, width: WIDTH, height: HEIGHT,
        borderRadius: "0px", boxShadow: "none" },
      video: { top: 0 },
      cutoutWindow: { top: 0, left: 0, width: WIDTH, height: HEIGHT },
      cutout: { top: 0 },
    };
  }

  function putGeometry(layout, time, initial) {
    const state = geometry(layout);
    const put = function (target, values) {
      if (initial) gsap.set(target, values);
      else tl.set(target, values, time);
    };
    put(presenterWindow, state.window);
    put(presenter, state.video);
    if (hasCutout) {
      put(cutoutWindow, state.cutoutWindow);
      put(cutout, state.cutout);
    }
  }

  putGeometry(beats[0].layout, 0, true);
  gsap.set(presenterWindow, { opacity: beats[0].layout === "graphic" ? 0 : 1 });
  if (hasCutout) gsap.set(cutoutWindow, { opacity: beats[0].layout === "split" ? 1 : 0 });

  let previousSection = null;
  beats.forEach(function (beat, position) {
    if (!["face", "split", "graphic"].includes(beat.layout)) {
      throw new Error("Unknown reel layout: " + beat.layout);
    }
    const section = el("section", "scene scene--" + beat.layout, null, graphics);
    section.id = "reel-scene-" + position;
    section.style.zIndex = String(position + 1);
    section.style.opacity = position === 0 ? "1" : "0";
    section.setAttribute("data-beat-id", String(beat.id || position));
    const content = el("div", "scene-content", null, section);

    if (beat.layout !== "face") {
      const builder = window.REEL_SCENES[beat.scene];
      if (!builder) throw new Error("Unknown reel scene: " + beat.scene);
      builder(content, beat, tl);
    }

    if (previousSection) {
      const at = beat.start;
      const transitionLength = Math.min(TRANSITION, Math.max(0.02, (beat.end - at) / 4));
      // This is the scene transition, not an early content exit. The outgoing
      // scene is held intact until the incoming scene starts.
      tl.to(previousSection, { opacity: 0, duration: transitionLength, ease: "sine.inOut" }, at);
      tl.fromTo(section, { opacity: 0 }, { opacity: 1, duration: transitionLength,
        ease: "sine.inOut", immediateRender: false }, at);
      tl.set(previousSection, { opacity: 0 }, at + transitionLength);

      const previousLayout = beats[position - 1].layout;
      if (beat.layout !== previousLayout) {
        const half = Math.min(TRANSITION / 2, at / 2);
        if (previousLayout !== "graphic") {
          tl.to(presenterWindow, { opacity: 0, duration: half, ease: "sine.inOut" }, at - half);
        }
        if (hasCutout && previousLayout === "split") {
          tl.to(cutoutWindow, { opacity: 0, duration: half, ease: "sine.inOut" }, at - half);
        }
        putGeometry(beat.layout, at, false);
        if (beat.layout !== "graphic") {
          tl.fromTo(presenterWindow, { opacity: 0 }, { opacity: 1, duration: half,
            ease: "sine.inOut", immediateRender: false }, at);
        } else tl.set(presenterWindow, { opacity: 0 }, at);
        if (hasCutout) {
          if (beat.layout === "split") {
            tl.fromTo(cutoutWindow, { opacity: 0 }, { opacity: 1, duration: half,
              ease: "sine.inOut", immediateRender: false }, at);
          } else tl.set(cutoutWindow, { opacity: 0 }, at);
        }
      }
    }
    previousSection = section;
  });

  const captionPositions = Object.assign({ face: 1320, split: 940, graphic: 1300 }, job.caption_positions || {});
  const measureContext = document.createElement("canvas").getContext("2d");

  function fitCaption(text, style) {
    const font = style === "serif" ? "Fraunces" : "Inter";
    const weight = style === "serif" ? 600 : 900;
    const baseSize = style === "serif" ? 112 : 104;
    let size = baseSize;
    if (measureContext) {
      // Width reserves room for the short scale entrance and word gaps.
      do {
        measureContext.font = (style === "serif" ? "italic " : "") + weight + " " + size + "px \"" + font + "\"";
        if (measureContext.measureText(text).width <= 870 || size <= 58) break;
        size -= 2;
      } while (size > 58);
    }
    return size;
  }

  const groups = (job.captions || []).slice().sort(function (a, b) { return a.start - b.start; });
  groups.forEach(function (group, index) {
    const start = Math.max(0, finite(group.start, 0));
    const nextStart = index + 1 < groups.length ? finite(groups[index + 1].start, duration) : duration;
    const end = Math.min(duration, finite(group.end, duration), nextStart);
    const text = String(group.text || "").trim();
    if (!text || end <= start) return;
    const layout = ["face", "split", "graphic"].includes(group.layout) ? group.layout : "face";
    const style = group.style === "serif" ? "serif" : "sans";
    const displayText = style === "sans" ? text.toLocaleUpperCase("en-US") : text;
    const caption = el("div", "caption-group caption--" + layout + " caption--" + style, null, captions);
    caption.id = "caption-" + index;
    caption.style.top = finite(captionPositions[layout], 1320) + "px";
    caption.style.fontSize = fitCaption(displayText, style) + "px";
    const emphasis = new Set(tokens(Array.isArray(group.emphasis) ? group.emphasis.join(" ") : group.emphasis));
    displayText.split(/\s+/).forEach(function (word) {
      const span = el("span", "caption-word", word, caption);
      if (tokens(word).some(function (token) { return emphasis.has(token); })) {
        span.classList.add("caption-word--emphasis");
      }
    });

    const enterLength = Math.min(0.085, (end - start) / 3);
    if (start <= 0.0001) {
      // The first spoken caption can be present on frame zero; a scale/position
      // entrance keeps that initial state visible rather than flashing blank.
      gsap.set(caption, { opacity: 1 });
      tl.from(caption, { y: 10, scale: 0.975, duration: enterLength,
        ease: "power3.out", immediateRender: true }, 0);
    } else {
      tl.fromTo(caption, { opacity: 0, y: 10, scale: 0.975 }, {
        opacity: 1, y: 0, scale: 1, duration: enterLength,
        ease: "power3.out", immediateRender: false,
      }, start);
    }
    const exitLength = Math.min(0.045, (end - start) / 8);
    tl.to(caption, { opacity: 0, duration: exitLength, ease: "power2.in" }, end - exitLength);
    tl.set(caption, { opacity: 0 }, end);
  });

  window.__timelines = window.__timelines || {};
  window.__timelines.main = tl;
  tl.seek(0, true);
})();
