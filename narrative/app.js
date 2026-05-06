/* ============================================================
 * Narrative Intelligence — App
 * ============================================================
 * Renders every module from window.NI. Designed so each render
 * function is independent and idempotent — it can be re-called
 * cheaply when state changes (e.g. user picks a different
 * dominant narrative, or the live tick mutates strengths).
 * ========================================================== */

(function () {
  "use strict";

  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const el = (tag, attrs = {}, ...kids) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "data") for (const [dk, dv] of Object.entries(v)) node.dataset[dk] = dv;
      else if (k === "html") node.innerHTML = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else if (v != null) node.setAttribute(k, v);
    }
    for (const kid of kids) {
      if (kid == null) continue;
      node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return node;
  };

  // Bind locals lazily — they may be replaced once we fetch data.json.
  let REGIME, REGIME_HISTORY, NARRATIVES, SIGNALS, MATRIX, CROSSASSET, PSYCHOLOGY, INSIGHTS, DEPENDENCIES, BACKTEST;
  function bindFromNI() {
    ({ REGIME, REGIME_HISTORY, NARRATIVES, SIGNALS, MATRIX, CROSSASSET, PSYCHOLOGY, INSIGHTS, DEPENDENCIES, BACKTEST } = window.NI);
  }
  bindFromNI();

  // Try to fetch a live snapshot from the scoring service (or its persisted
  // data.json). Falls back silently to the static window.NI on error.
  async function loadLiveData() {
    try {
      const res = await fetch("./data.json", { cache: "no-store" });
      if (!res.ok) throw new Error("no data.json");
      const live = await res.json();
      Object.assign(window.NI, live);
      bindFromNI();
      return { source: live.source || "live" };
    } catch (e) {
      try {
        // If the user is running scoring/server.py, /api/state will work too.
        const res = await fetch("/api/state", { cache: "no-store" });
        if (!res.ok) throw new Error("no api");
        const live = await res.json();
        Object.assign(window.NI, live);
        bindFromNI();
        return { source: live.source || "live" };
      } catch {
        return { source: "static-fallback" };
      }
    }
  }

  // App state — mutable so we can swap the dominant narrative
  // without re-executing every render path manually.
  const state = {
    dominantId: NARRATIVES.find(n => n.tier === "dominant")?.id || NARRATIVES[0].id,
    selectedCell: null,
    rotatorIndex: 0
  };

  // Sort tier so visual ordering reads dominant → rising → fading → latent → counter.
  const TIER_ORDER = { dominant: 0, rising: 1, fading: 2, latent: 3, counter: 4 };
  const trendClass = v => v > 0.3 ? "up" : v < -0.3 ? "down" : "flat";
  const fmtSigned = v => (v > 0 ? "+" : "") + v.toFixed(1);

  // ---- Top bar / clock / regime ------------------------------
  function renderTopbar() {
    $("#regime-text").textContent = `${REGIME.primary} · ${REGIME.secondary}`;
  }
  function renderClock() {
    const fmt = new Intl.DateTimeFormat("en-US", {
      hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
      timeZone: "America/New_York"
    });
    const tick = () => { $("#time-clock").textContent = `${fmt.format(new Date())} ET`; };
    tick();
    setInterval(tick, 1000);
  }

  // ---- Hero --------------------------------------------------
  function renderHero() {
    const n = NARRATIVES.find(x => x.id === state.dominantId) || NARRATIVES[0];

    $("#hero-title").textContent = n.name;
    $("#hero-summary").textContent = n.tagline;
    $("#hero-meta").textContent =
      `${n.ageWeeks} weeks active · regime confidence ${REGIME.conviction}%`;

    // Animate the meters from 0 → target.
    requestAnimationFrame(() => {
      $("#hero-strength").style.width = n.strength + "%";
      $("#hero-confirm").style.width = n.confirm + "%";
      $("#hero-dissent").style.width = n.dissent + "%";
    });
    $("#hero-strength-val").textContent = n.strength;
    $("#hero-confirm-val").textContent  = n.confirm;
    $("#hero-dissent-val").textContent  = n.dissent;

    const vCls = trendClass(n.velocity);
    const vEl = $("#hero-velocity");
    vEl.textContent = `${fmtSigned(n.velocity)}σ`;
    vEl.className = `velocity-val ${vCls}`;

    const tEl = $("#hero-trend");
    tEl.textContent = `7d trend ${fmtSigned(n.trend7)}`;
    tEl.className = `velocity-sub`;
  }

  function startRotator() {
    const lines = [
      d => `${d.name}: strength ${d.strength}, confirmation ${d.confirm}%, dissent ${d.dissent}%.`,
      d => `Drivers — ${d.drivers.slice(0, 2).join(" · ")}.`,
      d => d.against.length
        ? `Watch — ${d.against[0]}.`
        : `Confirming — ${d.with.slice(0, 2).join(" · ")}.`,
      d => `Tier: ${d.tier}. Polarity: ${d.polarity}.`
    ];
    const update = () => {
      const n = NARRATIVES.find(x => x.id === state.dominantId);
      const line = lines[state.rotatorIndex % lines.length](n);
      const node = $("#hero-rotator");
      node.style.opacity = "0";
      setTimeout(() => { node.textContent = line; node.style.opacity = "1"; }, 220);
      state.rotatorIndex++;
    };
    update();
    setInterval(update, 4500);
  }

  // ---- Tracker ----------------------------------------------
  function renderTracker() {
    const list = $("#tracker-list");
    list.innerHTML = "";

    const sorted = [...NARRATIVES].sort((a, b) => {
      if (TIER_ORDER[a.tier] !== TIER_ORDER[b.tier]) return TIER_ORDER[a.tier] - TIER_ORDER[b.tier];
      return b.strength - a.strength;
    });

    for (const n of sorted) {
      const tCls = n.trend7 > 0 ? "up" : n.trend7 < 0 ? "down" : "flat";
      const trendArrow = n.trend7 > 0 ? "▲" : n.trend7 < 0 ? "▼" : "■";

      const row = el("div", {
        class: `narr-row ${n.id === state.dominantId ? "active" : ""}`,
        role: "listitem",
        data: { id: n.id }
      },
        el("span", { class: `narr-tier ${n.tier}`, title: n.tier }),
        el("div", { class: "narr-name" }, n.name, el("small", {}, n.tagline)),
        el("div", { class: "narr-strength" }, String(n.strength)),
        el("div", { class: `narr-trend ${tCls}` }, `${trendArrow} ${fmtSigned(n.trend7)}`),
        el("div", { class: "narr-bar" },
          el("div", { class: "narr-bar-fill", style: `width:${n.confirm}%` })
        ),
        el("div", { class: "narr-confirm" }, `${n.confirm}%`)
      );

      row.addEventListener("click", () => {
        state.dominantId = n.id;
        $$(".narr-row").forEach(r => r.classList.toggle("active", r.dataset.id === n.id));
        renderHero();
        renderMatrix();
        renderCrossAsset();
        // restart rotator with new context
        state.rotatorIndex = 0;
      });

      list.appendChild(row);
    }
  }

  // ---- Psychology --------------------------------------------
  function renderPsychology() {
    const grid = $("#psy-grid");
    grid.innerHTML = "";

    for (const p of PSYCHOLOGY) {
      const arrow = p.dir > 0 ? "▲" : p.dir < 0 ? "▼" : "■";
      const aCls  = p.dir > 0 ? "up" : p.dir < 0 ? "down" : "flat";

      const cell = el("div", { class: `psy-cell ${p.color}` },
        el("div", { class: "psy-label" }, p.label),
        el("div", { class: "psy-row" },
          el("span", { class: "psy-value" }, String(p.value)),
          el("span", { class: `psy-arrow ${aCls}` }, arrow)
        ),
        el("div", { class: "psy-track" },
          el("div", { class: "psy-track-fill", style: `width:${p.value}%` })
        )
      );
      grid.appendChild(cell);
    }

    // Build a one-liner caption from the most extreme dimension.
    const sorted = [...PSYCHOLOGY].sort((a, b) =>
      Math.abs(b.value - 50) - Math.abs(a.value - 50));
    $("#psy-caption").textContent = sorted[0].caption;
  }

  // ---- Contradiction matrix ----------------------------------
  function renderMatrix() {
    const matrix = $("#matrix");
    matrix.innerHTML = "";

    // Header row
    matrix.appendChild(el("div", { class: "mh label" },
      el("strong", {}, "Narrative"),
      el("small", {}, "× signal")
    ));
    for (const sig of SIGNALS) {
      matrix.appendChild(el("div", { class: "mh" }, sig.label));
    }

    // Order narratives by tier so the dominant ones lead.
    const order = [...NARRATIVES].sort((a, b) =>
      (TIER_ORDER[a.tier] - TIER_ORDER[b.tier]) || (b.strength - a.strength));

    for (const n of order) {
      const row = MATRIX[n.id] || {};
      matrix.appendChild(el("div", { class: "mh label" },
        el("strong", {}, n.name),
        el("small", {}, `${n.tier} · str ${n.strength}`)
      ));
      for (const sig of SIGNALS) {
        const cell = row[sig.id] || { state: "ok", sev: 0, note: "—" };
        const dom = el("div", {
          class: `matrix-cell ${cell.state}`,
          data: { nid: n.id, sid: sig.id, state: cell.state, note: cell.note, narrName: n.name, sigLabel: sig.label, sev: cell.sev }
        },
          el("span", { class: "blob" }),
          el("span", { class: "sev" }, cell.sev.toFixed(2))
        );
        matrix.appendChild(dom);
      }
    }

    bindMatrixInteractions();
  }

  function bindMatrixInteractions() {
    const tip = $("#tooltip");
    const detail = $("#contradiction-detail");

    $$(".matrix-cell").forEach(cell => {
      cell.addEventListener("mousemove", e => {
        tip.hidden = false;
        tip.classList.add("visible");
        tip.className = `tooltip visible ${cell.dataset.state}`;
        tip.innerHTML =
          `<strong>${cell.dataset.state} · ${cell.dataset.sigLabel}</strong>` +
          `<div>${cell.dataset.narrName}</div>` +
          `<div style="margin-top:6px;color:var(--fg-3);">${cell.dataset.note}</div>`;
        const x = e.clientX, y = e.clientY;
        tip.style.left = Math.min(window.innerWidth - 340, x) + "px";
        tip.style.top  = Math.min(window.innerHeight - 120, y) + "px";
      });
      cell.addEventListener("mouseleave", () => {
        tip.classList.remove("visible");
        setTimeout(() => { if (!tip.classList.contains("visible")) tip.hidden = true; }, 150);
      });
      cell.addEventListener("click", () => {
        $$(".matrix-cell").forEach(c => c.classList.remove("active"));
        cell.classList.add("active");
        detail.hidden = false;
        $("#cd-eyebrow").textContent =
          `${cell.dataset.state.toUpperCase()} · ${cell.dataset.narrName} × ${cell.dataset.sigLabel} · severity ${cell.dataset.sev}`;
        $("#cd-body").textContent = cell.dataset.note;
      });
    });
  }

  // ---- Cross-asset confirmation ------------------------------
  function renderCrossAsset() {
    const grid = $("#ca-grid");
    grid.innerHTML = "";

    // Sort: highest confirm first, then by divergence intensity.
    const sorted = [...CROSSASSET].sort((a, b) => b.confirm - a.confirm);

    for (const a of sorted) {
      const item = el("div", { class: "ca-item", title: `${a.label} · ${a.cls}` },
        el("div", { class: "ca-head" },
          el("span", { class: "ca-label" }, a.label),
          el("span", { class: "ca-cls" }, a.cls)
        ),
        el("div", { class: "ca-bar" },
          el("div", { class: "ca-bar-confirm", style: `width:${a.confirm * 100}%` }),
          el("div", { class: "ca-bar-diverge", style: `width:${a.diverge * 100}%` })
        ),
        el("div", { class: "ca-meta" },
          el("span", { class: "conf" }, `confirm ${(a.confirm * 100).toFixed(0)}%`),
          el("span", { class: "div"  }, `diverge ${(a.diverge * 100).toFixed(0)}%`)
        ),
        el("div", { class: "ca-note" }, a.note)
      );
      grid.appendChild(item);
    }
  }

  // ---- Sparkline ---------------------------------------------
  function sparkline(values, opts = {}) {
    const w = opts.w || 220;
    const h = opts.h || 36;
    const pad = 2;
    if (!values.length) return null;

    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = Math.max(1, max - min);
    const stepX = (w - pad * 2) / (values.length - 1 || 1);

    const pts = values.map((v, i) => {
      const x = pad + i * stepX;
      const y = pad + (h - pad * 2) * (1 - (v - min) / span);
      return [x, y];
    });

    const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
    const fillPath = `${path} L${pts[pts.length - 1][0].toFixed(1)},${h} L${pts[0][0].toFixed(1)},${h} Z`;

    const lastUp = values[values.length - 1] >= values[0];
    const stroke = lastUp ? "var(--ok)" : "var(--coral)";
    const fill   = lastUp ? "rgba(84,217,156,.10)" : "rgba(240,105,120,.10)";

    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.setAttribute("preserveAspectRatio", "none");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", h);

    const fillEl = document.createElementNS(ns, "path");
    fillEl.setAttribute("d", fillPath);
    fillEl.setAttribute("fill", fill);
    svg.appendChild(fillEl);

    const lineEl = document.createElementNS(ns, "path");
    lineEl.setAttribute("d", path);
    lineEl.setAttribute("fill", "none");
    lineEl.setAttribute("stroke", stroke);
    lineEl.setAttribute("stroke-width", "1.5");
    lineEl.setAttribute("stroke-linecap", "round");
    lineEl.setAttribute("stroke-linejoin", "round");
    svg.appendChild(lineEl);

    // Last-point dot
    const last = pts[pts.length - 1];
    const dot = document.createElementNS(ns, "circle");
    dot.setAttribute("cx", last[0]);
    dot.setAttribute("cy", last[1]);
    dot.setAttribute("r", "2.2");
    dot.setAttribute("fill", stroke);
    svg.appendChild(dot);

    return svg;
  }

  // ---- Sentiment velocity ------------------------------------
  function renderVelocity() {
    const grid = $("#vel-grid");
    grid.innerHTML = "";

    const sorted = [...NARRATIVES].sort((a, b) => Math.abs(b.velocity) - Math.abs(a.velocity));

    for (const n of sorted) {
      const cls = trendClass(n.velocity);
      const item = el("div", { class: "vel-item" },
        el("div", { class: "vel-name" }, n.name),
        el("div", { class: `vel-vel ${cls}` }, `${fmtSigned(n.velocity)}σ`),
        el("div", { class: "vel-spark" }),
        el("div", { class: "vel-meta" },
          el("span", {}, `str ${n.strength}`),
          el("span", {}, `7d ${fmtSigned(n.trend7)}`),
          el("span", {}, `${n.tier}`)
        )
      );
      const sparkHost = item.querySelector(".vel-spark");
      const svg = sparkline(n.sparkline);
      if (svg) sparkHost.appendChild(svg);
      grid.appendChild(item);
    }
  }

  // ---- Insights ---------------------------------------------
  function renderInsights() {
    const list = $("#insight-list");
    list.innerHTML = "";
    for (const ins of INSIGHTS) {
      const item = el("li", { class: "insight-item" },
        el("span", { class: `insight-tag ${ins.tag}` }, ins.tag),
        el("span", { class: "insight-body" }, ins.body),
        el("span", { class: "insight-ts" }, ins.ts)
      );
      list.appendChild(item);
    }
  }

  // ---- Regime timeline ---------------------------------------
  function renderTimeline() {
    if (!REGIME_HISTORY || !REGIME_HISTORY.length) return;
    const earliest = Math.max(...REGIME_HISTORY.map(r => r.startWeeksAgo));
    const total = earliest;

    // Axis ticks at every 13 weeks (≈ quarterly)
    const axis = $("#tl-axis");
    axis.innerHTML = "";
    for (let w = total; w >= 0; w -= 13) {
      const left = ((total - w) / total) * 100;
      const tick = el("span", { class: "tick", style: `left:${left}%` },
        `${w}w`);
      axis.appendChild(tick);
    }

    const rows = $("#tl-rows");
    rows.innerHTML = "";

    // Group: each regime gets its own row so bars don't visually overlap.
    for (const r of REGIME_HISTORY) {
      const row = el("div", { class: "tl-row" });
      const left  = ((total - r.startWeeksAgo) / total) * 100;
      const right = ((total - r.endWeeksAgo)   / total) * 100;
      const width = Math.max(2, right - left);
      const isCurrent = r.endWeeksAgo === 0;
      const bar = el("div",
        { class: `tl-bar ${r.polarity || "neutral"} ${isCurrent ? "current" : ""}`,
          style: `left:${left}%; width:${width}%`,
          title: `${r.name} · ${r.startWeeksAgo}w → ${r.endWeeksAgo}w · peak ${r.peakStrength}\n${r.transitionReason}` },
        r.name,
        el("small", {}, `pk ${r.peakStrength}`)
      );
      row.appendChild(bar);
      rows.appendChild(row);
    }

    const last = REGIME_HISTORY[REGIME_HISTORY.length - 1];
    $("#tl-caption").textContent =
      `Regime cadence: ${REGIME_HISTORY.length} states across ~${total}w. ` +
      `Current state: ${last.name} (${last.startWeeksAgo}w in) — ${last.transitionReason}`;
  }

  // ---- Dependency graph (SVG) --------------------------------
  function renderDependencyGraph() {
    if (!DEPENDENCIES) return;
    const svg = $("#dg-svg");
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const NS = "http://www.w3.org/2000/svg";

    const nodeById = Object.fromEntries(DEPENDENCIES.nodes.map(n => [n.id, n]));

    // Arrowhead marker for direction
    const defs = document.createElementNS(NS, "defs");
    defs.innerHTML = `
      <marker id="arrow-ok" viewBox="0 0 10 10" refX="9" refY="5"
              markerWidth="5" markerHeight="5" orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10 z" fill="#54d99c"/>
      </marker>
      <marker id="arrow-bad" viewBox="0 0 10 10" refX="9" refY="5"
              markerWidth="5" markerHeight="5" orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10 z" fill="#f06978"/>
      </marker>`;
    svg.appendChild(defs);

    // Edges first so nodes paint on top.
    for (const e of DEPENDENCIES.edges) {
      const a = nodeById[e.from], b = nodeById[e.to];
      if (!a || !b) continue;
      // Slight quadratic curve so multi-edge pairs don't overlap visually.
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      const dx = b.x - a.x, dy = b.y - a.y;
      const norm = Math.hypot(dx, dy) || 1;
      const cx = mx + (-dy / norm) * 0.12;
      const cy = my + ( dx / norm) * 0.12;

      const path = document.createElementNS(NS, "path");
      path.setAttribute("d", `M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}`);
      path.setAttribute("class", `dg-edge ${e.type}`);
      path.setAttribute("stroke-opacity", String(0.35 + e.strength * 0.5));
      path.setAttribute("stroke-width", String(0.005 + e.strength * 0.025));
      path.setAttribute("marker-end",
        e.type === "reinforce" ? "url(#arrow-ok)" : "url(#arrow-bad)");
      path.style.cursor = "help";
      path.addEventListener("click", () => {
        const detail = $("#dg-detail");
        detail.hidden = false;
        $("#dg-eyebrow").textContent =
          `${e.type.toUpperCase()} · ${a.name} → ${b.name} · strength ${e.strength.toFixed(2)}`;
        $("#dg-body").textContent = e.note;
      });
      const title = document.createElementNS(NS, "title");
      title.textContent = `${e.type}: ${a.name} → ${b.name}\n${e.note}`;
      path.appendChild(title);
      svg.appendChild(path);
    }

    // Nodes
    for (const n of DEPENDENCIES.nodes) {
      const g = document.createElementNS(NS, "g");
      g.setAttribute("transform", `translate(${n.x}, ${n.y})`);
      const r = 0.045 + (n.strength / 100) * 0.05;

      const circle = document.createElementNS(NS, "circle");
      circle.setAttribute("class", `dg-node-circle ${n.tier}`);
      circle.setAttribute("r", String(r));
      circle.setAttribute("fill-opacity", "0.85");
      circle.setAttribute("stroke", "rgba(0,0,0,.5)");
      circle.setAttribute("stroke-width", "0.004");
      circle.addEventListener("click", () => {
        state.dominantId = n.id;
        $$(".narr-row").forEach(rr => rr.classList.toggle("active", rr.dataset.id === n.id));
        renderHero();
        renderMatrix();
        renderCrossAsset();
      });
      const t = document.createElementNS(NS, "title");
      t.textContent = `${n.name}\nstrength ${n.strength}\ntier ${n.tier}`;
      circle.appendChild(t);
      g.appendChild(circle);

      const lines = wrapName(n.name, 14);
      const label = document.createElementNS(NS, "text");
      label.setAttribute("class", "dg-node-label");
      label.setAttribute("y", String(r + 0.06));
      // Push labels outside the radius so they don't overlap circles.
      lines.forEach((line, i) => {
        const tspan = document.createElementNS(NS, "tspan");
        tspan.setAttribute("x", "0");
        tspan.setAttribute("dy", i === 0 ? "0" : "0.05");
        tspan.textContent = line;
        label.appendChild(tspan);
      });
      g.appendChild(label);
      svg.appendChild(g);
    }
  }

  function wrapName(name, max) {
    const words = name.split(" ");
    const lines = [""];
    for (const w of words) {
      const candidate = lines[lines.length - 1] ? lines[lines.length - 1] + " " + w : w;
      if (candidate.length <= max) lines[lines.length - 1] = candidate;
      else lines.push(w);
    }
    return lines.slice(0, 2);
  }

  // ---- Backtest ----------------------------------------------
  function renderBacktest() {
    if (!BACKTEST) return;
    const stats = BACKTEST.stats;
    const statsHost = $("#bt-stats");
    statsHost.innerHTML = "";

    const cells = [
      { label: "Events tracked",      value: String(stats.events) },
      { label: "Regime-break hit rate", value: stats.regimeBreakHitRate + "%",
        cls: stats.regimeBreakHitRate >= 50 ? "down" : "up" },
      { label: "Avg lead time",       value: stats.avgLeadDays + "d" },
      { label: "Avg market reaction", value: (stats.avgReactionPct >= 0 ? "+" : "") + stats.avgReactionPct + "%",
        cls: stats.avgReactionPct >= 0 ? "up" : "down" }
    ];
    for (const c of cells) {
      statsHost.appendChild(el("div", { class: "bt-stat" },
        el("div", { class: "bt-stat-label" }, c.label),
        el("div", { class: `bt-stat-value ${c.cls || ""}` }, c.value)
      ));
    }

    const tbody = $("#bt-tbody");
    tbody.innerHTML = "";
    const sorted = [...BACKTEST.events].sort((a, b) => a.detectedWeeksAgo - b.detectedWeeksAgo);
    for (const e of sorted) {
      const open = e.resolutionDays === null;
      const reactCls = open ? "" : (e.marketReactionPct >= 0 ? "up" : "down");
      const breakCell = open
        ? el("td", { class: "bt-open" }, "open")
        : (e.regimeBreak
            ? el("td", { class: "bt-break" }, "BROKE")
            : el("td", { class: "bt-no-break" }, "held"));
      const row = el("tr", {},
        el("td", {}, `${e.detectedWeeksAgo}w ago`),
        el("td", {}, e.narrative),
        el("td", {}, e.signal),
        el("td", { class: "num" }, e.severityAtDetection.toFixed(2)),
        el("td", { class: "num" }, open ? "—" : String(e.resolutionDays)),
        breakCell,
        el("td", { class: `num bt-react ${reactCls}` },
          open ? "—" : (e.marketReactionPct >= 0 ? "+" : "") + e.marketReactionPct + "%"),
        el("td", { class: "bt-lesson" }, e.lesson)
      );
      tbody.appendChild(row);
    }
  }

  // ---- Source indicator --------------------------------------
  function renderSource(source) {
    const pill = $("#source-pill");
    const text = $("#source-text");
    if (source === "scoring-pipeline" || source === "live") {
      pill.dataset.source = "live";
      text.textContent = "live · scoring";
    } else {
      pill.dataset.source = "static";
      text.textContent = "static";
    }
  }

  // ---- Live tick (subtle) ------------------------------------
  // The point: numbers should feel alive, not frozen.
  // We perturb strength slightly within a small bound and
  // re-render the bar widths only — never the labels — so the
  // overall read stays consistent but the surface breathes.
  function startLiveTick() {
    setInterval(() => {
      // tiny random walk on dominant narrative confirmation
      const node = $("#hero-confirm");
      if (!node) return;
      const cur = parseFloat(node.style.width || "0");
      const next = Math.max(20, Math.min(95, cur + (Math.random() - 0.5) * 1.6));
      node.style.width = next.toFixed(1) + "%";
    }, 3500);
  }

  // ---- Boot --------------------------------------------------
  async function boot() {
    // Paint the static fallback immediately so the user never sees a blank.
    paintAll();
    renderClock();
    startRotator();
    startLiveTick();
    renderSource(window.NI.source || "static-fallback");

    // Then upgrade to the live snapshot if available.
    const { source } = await loadLiveData();
    renderSource(source);
    // Reset selected dominant to the strongest narrative in the live data.
    if (window.NI.NARRATIVES && window.NI.NARRATIVES.length) {
      const strongest = [...window.NI.NARRATIVES].sort((a, b) => b.strength - a.strength)[0];
      if (strongest) state.dominantId = strongest.id;
    }
    paintAll();

    // Hide tooltip on scroll/click outside matrix
    document.addEventListener("scroll", () => {
      const tip = $("#tooltip");
      tip.classList.remove("visible");
    }, { passive: true });
  }

  function paintAll() {
    renderTopbar();
    renderHero();
    renderTracker();
    renderPsychology();
    renderTimeline();
    renderMatrix();
    renderCrossAsset();
    renderDependencyGraph();
    renderBacktest();
    renderVelocity();
    renderInsights();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
