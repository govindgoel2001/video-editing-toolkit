"""Card layouts and seekable GSAP motion adapted from the Desktop editor."""
CSS = {
 "opener": """
      #card { left:56px; top:56px; width:680px; padding:28px 40px 32px; }
      #l1, #l2 { font-size:62px; }
      #rule { width:0; height:6px; background:#e8b964; margin:18px 0 16px; }
 """,
 "chapter": """
      #card { left:556px; bottom:128px; width:1252px; padding:34px 44px 38px; }
      #t1 { font-size:66px; }
      #dot { position:absolute; right:40px; top:40px; width:13px; height:13px;
             border-radius:50%; background:#e8b964; }
 """,
 "stat": """
      #card { right:84px; top:150px; width:520px; padding:40px 44px 44px; }
      #num { font-family:Bahnschrift,"Segoe UI",system-ui,sans-serif;
             font-stretch:condensed; font-weight:700; font-size:150px;
             line-height:0.9; color:#f4f8f5; }
      #num span { color:#e8b964; font-size:88px; }
      #lab { font-family:"Segoe UI",system-ui,sans-serif; font-weight:600;
             font-size:27px; color:#c3d8cc; line-height:1.28; margin-top:14px; }
 """,
}

def body(c: dict) -> str:
    t = c["type"]
    if t == "opener":
        return f"""
      <div class="glass" id="card">
        <div class="edge"></div><div class="sheen" id="sheen"></div>
        <div class="kicker" id="kicker">{c['kicker']}</div>
        <div id="rule"></div>
        <span class="mask"><span class="title" id="l1">{c['l1']}</span></span>
        <span class="mask"><span class="title" id="l2">{c['l2']}</span></span>
        <div class="sub" id="sub" style="margin-top:22px">{c['sub']}</div>
      </div>"""
    if t == "chapter":
        return f"""
      <div class="glass" id="card">
        <div class="edge"></div><div class="sheen" id="sheen"></div>
        <div id="dot"></div>
        <div class="kicker" id="kicker">{c['kicker']}</div>
        <span class="mask" style="margin-top:12px">
          <span class="title" id="t1">{c['title']}</span></span>
      </div>"""
    unit = f"<span>{c['unit']}</span>" if c.get("unit") else ""
    return f"""
      <div class="glass" id="card">
        <div class="edge"></div><div class="sheen" id="sheen"></div>
        <div id="num">{c['num']}{unit}</div>
        <div id="lab">{c['label']}</div>
      </div>"""

def timeline(c: dict) -> str:
    d = float(c["dur"])
    out = d - 0.75
    # the card swings in on its own leading edge rather than sliding flat
    common = f"""
      tl.fromTo("#card", {{ opacity:0, x:-56, rotateY:-22, rotateX:5,
                            transformOrigin:"0% 50%" }},
        {{ opacity:1, x:0, rotateY:0, rotateX:0, duration:0.78,
           ease:"power3.out" }}, 0);
      tl.fromTo("#sheen", {{ x:-620 }}, {{ x:2100, duration:1.35,
           ease:"power2.inOut" }}, 0.22);
      tl.to("#card", {{ opacity:0, x:-34, rotateY:-14, duration:0.55,
           ease:"power2.in" }}, {out:.2f});
    """
    if c["type"] == "opener":
        return common + f"""
      tl.to("#rule", {{ width:196, duration:0.55, ease:"power3.out" }}, 0.42);
      tl.fromTo("#kicker", {{ opacity:0, y:10 }},
        {{ opacity:1, y:0, duration:0.45 }}, 0.30);
      tl.fromTo("#l1", {{ yPercent:110 }},
        {{ yPercent:0, duration:0.62, ease:"power3.out" }}, 0.52);
      tl.fromTo("#l2", {{ yPercent:110 }},
        {{ yPercent:0, duration:0.62, ease:"power3.out" }}, 0.66);
      tl.fromTo("#sub", {{ opacity:0, y:12 }},
        {{ opacity:1, y:0, duration:0.5 }}, 1.02);
        """
    if c["type"] == "chapter":
        return common + """
      tl.fromTo("#kicker", { opacity:0, y:8 },
        { opacity:1, y:0, duration:0.4 }, 0.26);
      tl.fromTo("#t1", { yPercent:112 },
        { yPercent:0, duration:0.6, ease:"power3.out" }, 0.40);
      tl.fromTo("#dot", { scale:0 },
        { scale:1, duration:0.4, ease:"back.out(3)" }, 0.55);
        """
    return common + """
      tl.fromTo("#num", { opacity:0, y:22, scale:0.92 },
        { opacity:1, y:0, scale:1, duration:0.6, ease:"power3.out" }, 0.28);
      tl.fromTo("#lab", { opacity:0, y:10 },
        { opacity:1, y:0, duration:0.45 }, 0.50);
        """
