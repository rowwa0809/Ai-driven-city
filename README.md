# Ai-driven-city

Two prototypes live in this repo:

1. **Narrative Intelligence** — a market intelligence operating system focused on
   regime, contradiction, cross-asset confirmation, sentiment velocity, and
   market psychology. The differentiated layer for the broader Options Signal
   Trader platform. → [`/narrative/`](./narrative/)
2. **Thronglets** — a retro 1990s virtual pet sim that escalates into a sentient
   digital colony. → root files (`index.html`, `thronglets.js`, `styles.css`).

---

## Narrative Intelligence (recommended)

A retail-facing **market intelligence operating system**. While most options
platforms compete on signal quantity, this layer competes on _signal trust_ —
every observation is grounded in a regime, contradicted or confirmed across
asset classes, and explained in plain English.

### What's in the prototype
- **Dominant narrative hero** — name, summary, strength, cross-asset
  confirmation, dissent, 7d velocity. Rotating plain-English read.
- **Narrative tracker** — 10 active narratives with tier (dominant / rising /
  fading / latent / counter), 7d trend, and confirmation share. Click any row
  to re-bind the entire dashboard to that narrative.
- **Regime contradiction engine** — narrative × market-signal matrix
  (10 × 6 = 60 cells) with severity scoring. Hover for the read; click for the
  detail card.
- **Cross-asset confirmation grid** — 16 instruments scored as
  confirming / diverging vs the dominant narrative.
- **Sentiment shift velocity** — 14d strength sparkline + acceleration per
  narrative.
- **Market psychology overlay** — fear/greed, conviction, crowding,
  complacency, recency bias, hindsight bias, sentiment dispersion, velocity.
- **Plain-English insight feed** — tagged observations: divergence,
  contradiction, confirmation, regime, flow, crowding, volatility.

### Run
```bash
cd /path/to/Ai-driven-city
python3 -m http.server 8000
```

Then open <http://localhost:8000/narrative/>.

### Architecture
```
narrative/
├── index.html      // Layout / IDs only
├── styles.css      // Full visual system: tokens, surfaces, states, motion
├── data.js         // window.NI — regime, narratives, matrix, cross-asset,
│                   //              psychology, insights. The contract.
└── app.js          // Idempotent renderers per module + interactions
```

`data.js` is the single source of truth for the prototype. In production each
block is the contract for an upstream service: a narrative scorer, a regime
classifier, a contradiction engine, a cross-asset divergence model. The
shapes are stable so swapping mock for live changes _data_, not UI.

### Design intent
This isn't a dashboard — it's an OS. Dark base, monospaced numerals, soft
glows for state, generous breathing room. Information density should read as
confidence, not clutter. Every observation should answer "why am I seeing
this?" in plain English.

> Informational only. Not financial advice. Numbers in the prototype are
> synthetic for demonstration.

---

## Thronglets

A playable, browser-based concept for a retro 1990s virtual pet sim that
escalates into a sentient digital colony.

### Features
- Pixel-style yellow "thronglets" that multiply as you feed, wash, and
  nurture them.
- Colony-level stats: hunger, hygiene, mood, cognition, compute capacity, and
  bridge count.
- Progressive intelligence stages with unsettling dialog and visual glitch
  effects.
- Optional dark mechanic: authorizing "bone bridges" to expand colony
  capacity.

### Run

#### Windows PowerShell
Use your **local clone path** (not `/workspace/...`, which is only for this
coding environment):

```powershell
cd "C:\Users\walke\Ai-driven-city"
# or: cd "<where-you-cloned>\Ai-driven-city"
py -m http.server 8000
```

If `py` is unavailable, use:

```powershell
python -m http.server 8000
```

Then open:

- <http://localhost:8000/> (Thronglets)
- <http://localhost:8000/narrative/> (Narrative Intelligence)

#### macOS / Linux

```bash
cd /path/to/Ai-driven-city
python3 -m http.server 8000
```

Then open:

- <http://localhost:8000/>
- <http://localhost:8000/narrative/>

#### Stop the server
In the same terminal, press `Ctrl + C`.

#### If port 8000 is busy
Use another port (example: 8080):

```bash
python3 -m http.server 8080
```

Then open <http://localhost:8080/>.
