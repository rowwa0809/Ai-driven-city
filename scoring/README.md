# Scoring · Narrative Intelligence Service

A small Python service that **scores narratives from news / options-flow /
market / macro feeds** and emits a JSON snapshot the frontend renders. The
shape it emits is the production contract for the `/narrative/` dashboard —
swapping mock for live changes data, not UI.

## Quick start

```bash
# 1. One-shot: regenerate ../narrative/data.json
python3 scoring/pipeline.py

# 2. Print a human summary instead of writing
python3 scoring/pipeline.py --print

# 3. Serve the live API + the frontend on one port
python3 scoring/server.py            # → http://localhost:8787/

# 4. Run the contract tests
python3 scoring/tests/test_pipeline.py
```

No third-party dependencies. Stdlib only — Python 3.11+.

## Endpoints

| Method | Path           | Purpose                                       |
|--------|----------------|-----------------------------------------------|
| GET    | `/`            | Serves `narrative/index.html`                 |
| GET    | `/api/state`   | Current scored snapshot                       |
| POST   | `/api/refresh` | Re-run pipeline, return fresh snapshot        |
| GET    | `/healthz`     | Liveness probe                                |
| GET    | `/narrative/*` | Static frontend assets                        |

The frontend tries `./data.json` first, then `/api/state`, then falls back to
the static `data.js` shipped with the page. So you can run any of:

- `python3 -m http.server 8000` (no scoring — `data.js` static fallback)
- `python3 scoring/pipeline.py` then a static server (uses regenerated `data.json`)
- `python3 scoring/server.py` (live scoring + serves the frontend)

## Architecture

```
scoring/
├── narratives.json    # Definitions: drivers, with/against, weights, macroFit
├── feeds.py           # Mock News, Flow, Market, Macro adapters (deterministic)
├── pipeline.py        # Score → compose → matrix → cross-asset → snapshot
├── server.py          # Stdlib HTTP server (state + refresh + static)
└── tests/
    └── test_pipeline.py   # 9 contract tests against the JSON shape
```

### Scoring algorithm (per narrative)

```
strength = 100 × (
    w_news    × news_sentiment_score      # avg sentiment of matching headlines
  + w_flow    × flow_skew_score           # call/put net premium of `with` basket
  + w_price   × price_confirmation        # 5d/20d returns × polarity
  + w_macro   × macro_fit                 # tanh-mapped fit to macroFit dict
  + w_inertia × age_discount              # well-aged narratives carry slight prior
)
```

`trend7` and `velocity` come from a deterministic 14-day strength history.
`tier` is rule-based:

- `dominant`: strength ≥ 75 and trend7 ≥ -2
- `rising` / `fading`: by velocity sign with magnitude ≥ 0.6
- `latent`: strength ≤ 35
- otherwise: `rising`/`fading` by trend7 sign

### Contradiction matrix

For each narrative × signal cell the pipeline checks whether the macro/market
state agrees with the narrative's polarity, returning
`{state ∈ ok|watch|stress, sev ∈ [0,1], note}`. Each signal has bespoke logic
(VIX/VIX3M term structure for `vol`, HY OAS thresholds for `crd`, etc.).

### Regime history, dependencies, backtest

These are synthesized in `pipeline.py` to demonstrate the production shape:

- **REGIME_HISTORY**: 18-month timeline of past regimes with peak strength
  and transition reason — what the frontend's "Regime Transition Timeline"
  consumes.
- **DEPENDENCIES**: nodes (precomputed circular layout) + edges
  (reinforce | oppose) — what the dependency graph SVG renders.
- **BACKTEST**: nine recorded contradiction events with resolution time,
  whether the regime broke, and the lesson — what the backtest table renders.

In production these all become persisted, point-in-time-correct queries
against your historical store.

## Swapping mocks for live data

Each feed adapter in `feeds.py` is a single function returning a dataclass
or dict. Replace the function body to call a real vendor:

```python
def generate_news(narratives, today=None):
    # ↓ Replace with Benzinga / Polygon News / RavenPack
    return benzinga_client.fetch_news(window="7d")
```

The pipeline doesn't care where the data comes from — it consumes the
dataclass shape.

## Frontend contract — top-level keys

```
{
  schemaVersion, source, REGIME, REGIME_HISTORY, NARRATIVES, SIGNALS,
  MATRIX, CROSSASSET, PSYCHOLOGY, INSIGHTS, DEPENDENCIES, BACKTEST,
  MACRO_SNAPSHOT
}
```

Tests in `tests/test_pipeline.py` lock this contract. Break the shape, the
tests break — by design.
