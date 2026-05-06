/* ============================================================
 * Narrative Intelligence · synthetic dataset
 * ============================================================
 * This file is the single source of truth for the prototype.
 * In production, each block here is the contract for a real
 * upstream service: a narrative scorer, a regime classifier,
 * a cross-asset divergence engine, and so on. The shapes are
 * deliberately stable so that swapping mock for live changes
 * data, not UI.
 * ========================================================== */

window.NI = (function () {
  // ---- Regime ---------------------------------------------------
  const REGIME = {
    primary: "Late-cycle expansion",
    secondary: "Disinflationary tilt · fiscal overhang",
    riskOn: 0.38,           // [-1 risk-off, +1 risk-on]
    consensus: 71,          // % of narratives aligned with primary
    conviction: 58,         // model confidence in regime label
    ageWeeks: 14,
    transitionProb: 0.31,   // chance of regime break in next 6w
    asOf: "2026-05-06 14:32 ET"
  };

  // ---- Narratives ----------------------------------------------
  // strength: 0–100 composite (flow + price + sentiment + macro)
  // trend7:   7d delta in strength
  // velocity: 14d acceleration (z-score on Δstrength)
  // confirm:  cross-asset confirmation share, 0–100
  // dissent:  share of correlated assets diverging, 0–100
  // tier:     dominant | rising | fading | latent | counter
  const NARRATIVES = [
    {
      id: "ai-supercycle",
      name: "AI Supercycle",
      tagline: "Hyperscaler capex sustains semiconductor & power demand into 2027.",
      strength: 78, trend7: -3, velocity: -0.4,
      confirm: 64, dissent: 36, ageWeeks: 92,
      tier: "dominant", polarity: "bullish-equity",
      drivers: ["NVDA capex guides", "Hyperscaler 2026 capex +28% YoY", "TSMC CoWoS utilization"],
      with: ["SOX", "Power utilities", "Long-dated copper"],
      against: ["Memory cyclicals", "Grid permit backlog", "AI ROI scrutiny"],
      sparkline: [70,72,74,76,78,79,81,82,83,82,80,79,78,78]
    },
    {
      id: "soft-landing",
      name: "Soft Landing",
      tagline: "Inflation glides to 2-handle without breaking labor market.",
      strength: 66, trend7: -5, velocity: -0.7,
      confirm: 51, dissent: 49, ageWeeks: 18,
      tier: "fading", polarity: "bullish-risk",
      drivers: ["Core services ex-shelter cooling", "Wage growth easing", "Productivity surprise"],
      with: ["IG credit spreads tight", "Cyclicals leadership"],
      against: ["VIX term inversion 3/8d", "Truck tonnage softening"],
      sparkline: [70,71,72,73,72,71,70,69,68,67,67,66,66,66]
    },
    {
      id: "higher-for-longer",
      name: "Higher-for-Longer",
      tagline: "Sticky services + fiscal supply keep real rates elevated.",
      strength: 61, trend7: +6, velocity: +1.1,
      confirm: 58, dissent: 42, ageWeeks: 31,
      tier: "rising", polarity: "bearish-duration",
      drivers: ["10y term premium re-pricing", "Coupon size revisions", "Owner-equiv rent stickiness"],
      with: ["Front-end yields", "USD"],
      against: ["Long-duration tech multiples", "REIT cap rates"],
      sparkline: [52,53,53,54,55,56,57,58,58,59,60,60,61,61]
    },
    {
      id: "reshoring",
      name: "Reshoring & Capex Boom",
      tagline: "IRA/CHIPS afterglow + national-security capex floor.",
      strength: 54, trend7: +1, velocity: +0.2,
      confirm: 47, dissent: 53, ageWeeks: 78,
      tier: "rising", polarity: "structural",
      drivers: ["Construction spend ex-resi", "Industrial backlogs", "DoD obligations"],
      with: ["Industrials breadth", "Electrical equipment"],
      against: ["Permitting drag", "Labor cost pass-through"],
      sparkline: [48,49,49,50,51,52,52,53,53,54,54,54,54,54]
    },
    {
      id: "energy-stress",
      name: "Energy Transition Stress",
      tagline: "Power grid + uranium can't keep up with AI/EV demand curve.",
      strength: 64, trend7: +9, velocity: +1.6,
      confirm: 71, dissent: 29, ageWeeks: 24,
      tier: "rising", polarity: "structural-bullish-commodities",
      drivers: ["Datacenter MW queue", "Uranium spot tightness", "Transmission backlog"],
      with: ["Utilities", "Uranium miners", "Copper futures"],
      against: ["Battery oversupply", "Solar polysilicon glut"],
      sparkline: [50,51,53,54,55,57,58,59,60,61,62,63,64,64]
    },
    {
      id: "bond-vigilantes",
      name: "Bond Vigilantes Returning",
      tagline: "Term premium normalizes as fiscal path becomes the story.",
      strength: 49, trend7: +7, velocity: +1.3,
      confirm: 44, dissent: 56, ageWeeks: 9,
      tier: "rising", polarity: "bearish-duration",
      drivers: ["Net coupon supply Q3", "Foreign UST share dropping", "5y5y inflation drift"],
      with: ["Steepener flows", "Gold"],
      against: ["Equity multiple expansion"],
      sparkline: [38,39,40,41,42,43,44,45,46,47,48,48,49,49]
    },
    {
      id: "dxy-wrecking",
      name: "Dollar Wrecking Ball",
      tagline: "USD strength compresses non-US earnings & EM liquidity.",
      strength: 41, trend7: -2, velocity: -0.3,
      confirm: 39, dissent: 61, ageWeeks: 12,
      tier: "latent", polarity: "bearish-em",
      drivers: ["Rate-diff carry", "Safe-haven bid Q1"],
      with: ["EM FX weakness", "Gold (paradox)"],
      against: ["Cyclical commodity strength"],
      sparkline: [44,44,43,43,42,42,42,41,41,41,40,41,41,41]
    },
    {
      id: "china-stimulus",
      name: "China Stimulus Hopium",
      tagline: "Property backstop + consumer subsidies — credible or stage-managed?",
      strength: 33, trend7: -4, velocity: -0.6,
      confirm: 27, dissent: 73, ageWeeks: 7,
      tier: "fading", polarity: "tactical-bullish",
      drivers: ["PBoC RRR cuts", "Property white-list"],
      with: ["KWEB", "Iron ore short-cover"],
      against: ["Credit impulse still negative"],
      sparkline: [42,41,40,39,38,37,36,35,34,34,33,33,33,33]
    },
    {
      id: "geopolitical",
      name: "Geopolitical Premium",
      tagline: "Strait + Gulf risk repriced into oil & defense.",
      strength: 58, trend7: +3, velocity: +0.5,
      confirm: 55, dissent: 45, ageWeeks: 35,
      tier: "rising", polarity: "tail-risk",
      drivers: ["Shipping insurance rates", "Defense order books"],
      with: ["Defense primes", "Brent backwardation"],
      against: ["Risk asset complacency"],
      sparkline: [54,54,55,55,56,56,57,57,57,58,58,58,58,58]
    },
    {
      id: "crypto-rerating",
      name: "Crypto Re-rating",
      tagline: "ETF flows + sovereign adoption move BTC into reserve discourse.",
      strength: 47, trend7: -1, velocity: 0.0,
      confirm: 35, dissent: 65, ageWeeks: 16,
      tier: "latent", polarity: "speculative",
      drivers: ["Spot ETF AUM", "Halving supply effect"],
      with: ["Miners", "ETH staking yields"],
      against: ["Liquidity sensitivity to real rates"],
      sparkline: [50,50,49,49,48,48,48,47,47,47,47,47,47,47]
    }
  ];

  // ---- Contradiction matrix ------------------------------------
  // Each cell: state ∈ {ok, watch, stress}, severity 0–1, note.
  const SIGNALS = [
    { id: "vol",   label: "Vol term structure" },
    { id: "brd",   label: "Equity breadth" },
    { id: "crd",   label: "Credit spreads" },
    { id: "rates", label: "Rates / curve" },
    { id: "fx",    label: "FX / DXY" },
    { id: "flow",  label: "Retail vs dealer flow" }
  ];

  // matrix[narrativeId][signalId] = {state, sev, note}
  const MATRIX = {
    "ai-supercycle": {
      vol:   { state: "watch",  sev: 0.55, note: "VIX1M/3M flatter than realized; tail bid building under index-level calm." },
      brd:   { state: "stress", sev: 0.78, note: "Top 7 names = 91% of YTD index return. Equal-weight breadth diverging." },
      crd:   { state: "ok",     sev: 0.20, note: "IG/HY tight; no credit objection to capex story." },
      rates: { state: "watch",  sev: 0.50, note: "Long-end repricing pressuring multiples on long-duration AI." },
      fx:    { state: "ok",     sev: 0.25, note: "USD neutral for hyperscaler earnings translation." },
      flow:  { state: "stress", sev: 0.72, note: "Retail call skew vs dealer net-short gamma into AI single names." }
    },
    "soft-landing": {
      vol:   { state: "stress", sev: 0.81, note: "VIX/VIX3M inverted 3 of last 8 sessions despite SPX ATH." },
      brd:   { state: "watch",  sev: 0.55, note: "Defensives outperforming on up days — quietly." },
      crd:   { state: "ok",     sev: 0.18, note: "HY OAS at cycle tights; no recession premium." },
      rates: { state: "watch",  sev: 0.48, note: "2s10s steepening on supply, not on growth." },
      fx:    { state: "ok",     sev: 0.30, note: "DXY range-bound; consistent with Goldilocks read." },
      flow:  { state: "watch",  sev: 0.52, note: "Hedging activity in SPX puts up 22% MoM despite calm tape." }
    },
    "higher-for-longer": {
      vol:   { state: "watch",  sev: 0.50, note: "MOVE elevated vs VIX — bond vol leads." },
      brd:   { state: "ok",     sev: 0.30, note: "Cyclicals participating; not a defensive flight." },
      crd:   { state: "ok",     sev: 0.25, note: "Spreads still tight; no funding stress signal." },
      rates: { state: "ok",     sev: 0.18, note: "Front-end pricing one cut max; aligned." },
      fx:    { state: "ok",     sev: 0.22, note: "DXY firm; rate-diff supportive." },
      flow:  { state: "watch",  sev: 0.45, note: "Long-duration ETFs seeing outflows again." }
    },
    "reshoring": {
      vol:   { state: "ok",     sev: 0.20, note: "Industrials vol behaving; no panic." },
      brd:   { state: "ok",     sev: 0.25, note: "Mid-cap industrials outperforming." },
      crd:   { state: "ok",     sev: 0.15, note: "Investment-grade industrials tightening." },
      rates: { state: "watch",  sev: 0.50, note: "Real rates pressuring construction financing." },
      fx:    { state: "watch",  sev: 0.45, note: "Strong USD complicates export competitiveness." },
      flow:  { state: "ok",     sev: 0.30, note: "Institutional accumulation in machinery names." }
    },
    "energy-stress": {
      vol:   { state: "watch",  sev: 0.55, note: "Uranium realized vol elevated; spot moves on inventory drips." },
      brd:   { state: "ok",     sev: 0.25, note: "Utilities outperforming with rates rising — atypical." },
      crd:   { state: "ok",     sev: 0.20, note: "Utility credit holding; capex finance-able." },
      rates: { state: "watch",  sev: 0.50, note: "Capex-heavy utilities sensitive to long end." },
      fx:    { state: "ok",     sev: 0.20, note: "Dollar-neutral for thesis." },
      flow:  { state: "ok",     sev: 0.30, note: "Real-money rotating into power-grid plays." }
    },
    "bond-vigilantes": {
      vol:   { state: "stress", sev: 0.76, note: "MOVE / VIX ratio at 6m highs; rates tail driving cross-asset risk." },
      brd:   { state: "watch",  sev: 0.50, note: "REIT, utilities, low-vol underperforming on supply days." },
      crd:   { state: "watch",  sev: 0.50, note: "IG basis under pressure during auction concessions." },
      rates: { state: "stress", sev: 0.82, note: "Term premium re-emerging; auctions tailing." },
      fx:    { state: "ok",     sev: 0.30, note: "DXY mostly firm; not yet flight scenario." },
      flow:  { state: "watch",  sev: 0.55, note: "Foreign UST share lowest since 2009." }
    },
    "dxy-wrecking": {
      vol:   { state: "ok",     sev: 0.30, note: "FX vol contained; managed range." },
      brd:   { state: "watch",  sev: 0.45, note: "Multinational EPS revisions softening." },
      crd:   { state: "watch",  sev: 0.50, note: "EM HY widening at the margin." },
      rates: { state: "ok",     sev: 0.35, note: "Differentials still favor USD modestly." },
      fx:    { state: "stress", sev: 0.72, note: "EMFX basket making fresh lows on rate-diff carry." },
      flow:  { state: "watch",  sev: 0.40, note: "EM ETF outflows re-accelerating." }
    },
    "china-stimulus": {
      vol:   { state: "watch",  sev: 0.55, note: "HSI implied vol bid into stimulus rumor cadence." },
      brd:   { state: "stress", sev: 0.70, note: "Property names rallying without consumer follow-through." },
      crd:   { state: "watch",  sev: 0.50, note: "Asia HY spreads not confirming rally." },
      rates: { state: "ok",     sev: 0.25, note: "CGB curve steady." },
      fx:    { state: "watch",  sev: 0.55, note: "CNY fix anchoring; not a signal of strength." },
      flow:  { state: "stress", sev: 0.75, note: "Foreign investors net sellers despite headlines." }
    },
    "geopolitical": {
      vol:   { state: "watch",  sev: 0.50, note: "Brent vol > equity vol; energy tail bid present." },
      brd:   { state: "ok",     sev: 0.30, note: "Defense breadth strong." },
      crd:   { state: "ok",     sev: 0.25, note: "EM exporter spreads stable." },
      rates: { state: "ok",     sev: 0.30, note: "Safe-haven bid muted; supply story dominates." },
      fx:    { state: "watch",  sev: 0.40, note: "Petro-currencies firmer." },
      flow:  { state: "ok",     sev: 0.35, note: "Defense ETFs absorbing flows." }
    },
    "crypto-rerating": {
      vol:   { state: "watch",  sev: 0.55, note: "BTC realized vol falling — institutionalization or apathy?" },
      brd:   { state: "watch",  sev: 0.50, note: "Miners diverging from BTC spot." },
      crd:   { state: "ok",     sev: 0.25, note: "No crypto-credit reflexivity yet." },
      rates: { state: "stress", sev: 0.70, note: "Real-rate sensitivity reasserts during higher-for-longer regime." },
      fx:    { state: "ok",     sev: 0.30, note: "USD-neutral on net flows." },
      flow:  { state: "watch",  sev: 0.55, note: "Spot ETF flows decelerating from Q1 pace." }
    }
  };

  // ---- Cross-asset confirmation --------------------------------
  // For each major asset, scored vs the dominant narrative.
  // confirm + diverge ≤ 1; remainder is neutral.
  const CROSSASSET = [
    { id:"spx",  label:"S&P 500",         cls:"Equities",   confirm: 0.71, diverge: 0.18, note: "Index level confirms; breadth disputes." },
    { id:"ndx",  label:"Nasdaq 100",      cls:"Equities",   confirm: 0.83, diverge: 0.10, note: "Concentration confirmation; not breadth confirmation." },
    { id:"rty",  label:"Russell 2000",    cls:"Equities",   confirm: 0.34, diverge: 0.55, note: "Small caps reject AI-led growth read." },
    { id:"sox",  label:"PHLX SOX",        cls:"Equities",   confirm: 0.78, diverge: 0.12, note: "Direct beneficiary; aligned." },
    { id:"xlu",  label:"Utilities",       cls:"Equities",   confirm: 0.62, diverge: 0.20, note: "Power demand thesis confirming, decoupled from rates." },
    { id:"hyg",  label:"HY credit",       cls:"Credit",     confirm: 0.55, diverge: 0.25, note: "Tight spreads endorse; complacent if cycle late." },
    { id:"lqd",  label:"IG credit",       cls:"Credit",     confirm: 0.60, diverge: 0.18, note: "Stable; consistent with capex story." },
    { id:"tlt",  label:"20+ UST",         cls:"Rates",      confirm: 0.22, diverge: 0.62, note: "Long bonds rejecting soft-landing pricing." },
    { id:"ief",  label:"7-10y UST",       cls:"Rates",      confirm: 0.30, diverge: 0.50, note: "Term premium pressuring belly." },
    { id:"dxy",  label:"DXY",             cls:"FX",         confirm: 0.41, diverge: 0.32, note: "Range-bound; mild divergence." },
    { id:"emfx", label:"EM FX",           cls:"FX",         confirm: 0.20, diverge: 0.65, note: "EM weakness contradicts global growth confirmation." },
    { id:"cl",   label:"WTI crude",       cls:"Commodity",  confirm: 0.48, diverge: 0.35, note: "Backwardation supportive; supply story noisy." },
    { id:"hg",   label:"Copper",          cls:"Commodity",  confirm: 0.66, diverge: 0.18, note: "Confirms electrification + AI power demand." },
    { id:"gold", label:"Gold",            cls:"Commodity",  confirm: 0.52, diverge: 0.30, note: "Paradox — confirms via central-bank bid; diverges via real rates." },
    { id:"u",    label:"Uranium",         cls:"Commodity",  confirm: 0.74, diverge: 0.10, note: "Tight spot — base-load AI thesis." },
    { id:"btc",  label:"Bitcoin",         cls:"Crypto",     confirm: 0.39, diverge: 0.42, note: "ETF flows decelerating; thesis loses tactical confirmation." }
  ];

  // ---- Market psychology --------------------------------------
  // 0–100 indices, with directional read.
  const PSYCHOLOGY = [
    { id:"fg",      label:"Fear / Greed",        value: 64, dir:+1, color:"warm",  caption:"Greed-side; not extreme. Crowding rising." },
    { id:"conv",    label:"Conviction",          value: 58, dir:-1, color:"cool",  caption:"Conviction softening as narrative dispersion widens." },
    { id:"crowd",   label:"Crowding",            value: 72, dir:+1, color:"hot",   caption:"Top-decile crowding in Mag-7 + AI-power basket." },
    { id:"compl",   label:"Complacency",         value: 55, dir:+1, color:"warm",  caption:"Implied skew compressed; tails priced cheap." },
    { id:"recency", label:"Recency Bias",        value: 67, dir:+1, color:"warm",  caption:"Trailing 3m returns extrapolated heavily into surveys." },
    { id:"hindsight", label:"Hindsight Bias",    value: 49, dir: 0, color:"cool",  caption:"Soft-landing being narrated as obvious in retrospect." },
    { id:"disp",    label:"Sentiment Dispersion",value: 41, dir:-1, color:"cool",  caption:"Bears thinning; lower dispersion = fragility." },
    { id:"vela",    label:"Velocity (Δ)",        value: 53, dir:+1, color:"warm",  caption:"Net narrative shifts accelerating week-over-week." }
  ];

  // ---- Insight feed (plain English) ---------------------------
  const INSIGHTS = [
    { tag:"DIVERGENCE",     ts:"-7m",  body:"AI supercycle narrative weakening despite semiconductor index momentum — breadth, not headlines, is the read."},
    { tag:"CONTRADICTION",  ts:"-12m", body:"Bond market contradicting equity optimism: term premium repricing while SPX prints fresh highs."},
    { tag:"REGIME",         ts:"-21m", body:"Market pricing soft landing while volatility term structure has inverted 3 of last 8 sessions."},
    { tag:"FLOW",           ts:"-26m", body:"Retail call activity in AI single-names detached from macro liquidity conditions."},
    { tag:"CONFIRMATION",   ts:"-34m", body:"Energy-stress thesis gaining: utilities outperforming with rates rising — atypical and supportive."},
    { tag:"REGIME",         ts:"-42m", body:"Higher-for-longer narrative regaining strength as long-end yields refuse to confirm cuts."},
    { tag:"CROWDING",       ts:"-58m", body:"Conviction softening even as crowding rises — fragility signature, not strength."},
    { tag:"CHINA",          ts:"-1h",  body:"Stimulus narrative fading: foreign investors net sellers despite property white-list headlines."},
    { tag:"DIVERGENCE",     ts:"-1h",  body:"Russell 2000 rejecting AI-led growth read; small-caps not following the index up."},
    { tag:"VOLATILITY",     ts:"-2h",  body:"MOVE/VIX ratio at 6m highs — rates tail is leading, not lagging."}
  ];

  // ---- Helper: lookup by id -----------------------------------
  function byId(arr, id) { return arr.find(x => x.id === id); }

  return { REGIME, NARRATIVES, SIGNALS, MATRIX, CROSSASSET, PSYCHOLOGY, INSIGHTS, byId };
})();
