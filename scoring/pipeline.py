"""
Narrative scoring pipeline.

End-to-end:
    1. Load narrative definitions from narratives.json.
    2. Pull mock feeds (news, options flow, market, macro).
    3. Score each narrative across 5 dimensions, compose strength.
    4. Compute trend / velocity from a synthetic 14-day history.
    5. Build the contradiction matrix narrative × signal.
    6. Score cross-asset confirmation vs the dominant narrative.
    7. Compose market-psychology composites.
    8. Generate plain-English insights.
    9. Synthesize regime history, dependency graph, backtest events.
   10. Emit a JSON snapshot matching the frontend's window.NI contract.

Run:
    python3 -m scoring.pipeline                 # writes ../narrative/data.json
    python3 -m scoring.pipeline --print         # prints summary
    python3 -m scoring.pipeline --out path.json # custom out path
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
import argparse
import json
import math
import statistics

from feeds import (
    NewsItem, FlowSnapshot, MarketSnapshot, MacroSnapshot,
    generate_news, generate_flow, generate_market, generate_macro,
    generate_strength_history, seeded_rng,
)


HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "narratives.json"
DEFAULT_OUT = HERE.parent / "narrative" / "data.json"


# ============================================================
#  Score components
# ============================================================

def _polarity_sign(polarity: str) -> int:
    """Map a narrative polarity tag to ±1 for sign-aware scoring."""
    bullish = {"bullish-equity", "bullish-risk", "tactical-bullish",
               "structural-bullish-commodities", "speculative", "structural"}
    bearish = {"bearish-duration", "bearish-em", "tail-risk"}
    if polarity in bullish: return +1
    if polarity in bearish: return -1
    return +1  # default: thesis-true is "positive"

def score_news(narrative: dict, news: List[NewsItem]) -> Tuple[float, int]:
    """Return (score in [0,1], n_matched). Sign-aware to narrative polarity."""
    nid = narrative["id"]
    matched = [n for n in news if nid in n.topics]
    if not matched: return 0.5, 0
    # Sentiment normalized to [0, 1]; sign expressed by polarity.
    sign = _polarity_sign(narrative["polarity"])
    avg = statistics.fmean(item.sentiment for item in matched)
    centered = (sign * avg + 1) / 2
    # Volume kicker: a wider crowd talking about it lifts the score modestly.
    volume_kicker = min(0.15, len(matched) / 60)
    return max(0.0, min(1.0, centered + volume_kicker)), len(matched)

def score_flow(narrative: dict, flow: Dict[str, FlowSnapshot]) -> float:
    """Skew of net call-vs-put premium across the narrative's `with` symbols."""
    syms = narrative.get("with", [])
    sign = _polarity_sign(narrative["polarity"])
    skews = []
    for s in syms:
        snap = flow.get(s)
        if snap: skews.append(snap.cp_skew)
    if not skews: return 0.5
    raw = statistics.fmean(skews) * sign
    return max(0.0, min(1.0, (raw + 1) / 2))

def score_price(narrative: dict, market: Dict[str, MarketSnapshot]) -> float:
    """Sign-aware 5d/20d returns across `with` minus `against`."""
    sign = _polarity_sign(narrative["polarity"])
    pos_rets, neg_rets = [], []
    for s in narrative.get("with", []):
        snap = market.get(s)
        if snap: pos_rets.append(0.6 * snap.ret_5d + 0.4 * snap.ret_20d)
    for s in narrative.get("against", []):
        snap = market.get(s)
        if snap: neg_rets.append(0.6 * snap.ret_5d + 0.4 * snap.ret_20d)
    spread = (statistics.fmean(pos_rets) if pos_rets else 0) \
           - (statistics.fmean(neg_rets) if neg_rets else 0)
    # Map a typical 5-day spread of ±2% into roughly [0, 1].
    return max(0.0, min(1.0, 0.5 + sign * spread * 18))

def score_macro(narrative: dict, macro: MacroSnapshot) -> float:
    """For each macro indicator the narrative cares about, check the sign matches."""
    fits = narrative.get("macroFit", {})
    if not fits: return 0.5
    # Simple normalization for each indicator vs a midpoint.
    midpoints = {
        "ten_year_yield": 4.3, "real_rates": 1.95, "dxy": 104.0,
        "vix": 17.5, "fed_funds": 4.75, "cpi_yoy": 2.9,
        "industrial_production": 1.0, "credit_spread": 330.0,
        "term_premium": 15.0, "breadth": 0.0,
    }
    contribs = []
    for k, want in fits.items():
        val = getattr(macro, k, None)
        if val is None: continue
        if want == 0:  # only matters that it's not extreme
            mid = midpoints.get(k, val)
            dev = abs(val - mid) / max(1, mid)
            contribs.append(max(0.0, 1.0 - dev * 1.5))
            continue
        mid = midpoints.get(k, val)
        diff = (val - mid) / max(1e-3, abs(mid))
        # want=+1 → higher is better; want=-1 → lower is better
        score = 0.5 + 0.5 * math.tanh(2 * diff * want)
        contribs.append(score)
    return statistics.fmean(contribs) if contribs else 0.5

def score_inertia(narrative: dict) -> float:
    """Older, well-established narratives carry slight extra weight."""
    age = narrative.get("ageWeeks", 0)
    return max(0.3, min(0.85, 0.4 + math.log1p(age) * 0.08))


# ============================================================
#  Narrative composer
# ============================================================

@dataclass
class ScoredNarrative:
    spec: dict
    components: Dict[str, float]
    strength: float
    trend7: float
    velocity: float
    confirm: float
    dissent: float
    sparkline: List[float]
    tier: str
    reads: List[str]              # plain-english reads, used for the rotator + insights


def score_narrative(spec: dict, news, flow, market, macro) -> ScoredNarrative:
    components = {
        "news":   score_news(spec, news)[0],
        "flow":   score_flow(spec, flow),
        "price":  score_price(spec, market),
        "macro":  score_macro(spec, macro),
        "inertia": score_inertia(spec),
    }
    weights = spec.get("weights", {"news": .3, "flow": .2, "price": .2, "macro": .2, "inertia": .1})
    composite = sum(components[k] * weights.get(k, 0) for k in components)
    strength = round(composite * 100, 1)

    sparkline = generate_strength_history(spec["id"], strength)
    trend7 = round(sparkline[-1] - sparkline[-8], 1) if len(sparkline) >= 8 else 0.0
    if len(sparkline) >= 5:
        deltas = [sparkline[i] - sparkline[i - 1] for i in range(-4, 0)]
        if statistics.pstdev(deltas) > 1e-6:
            velocity = round((statistics.fmean(deltas) - 0)
                             / max(0.5, statistics.pstdev(deltas)), 2)
        else:
            velocity = 0.0
    else:
        velocity = 0.0

    # Confirmation = share of `with` symbols whose price agrees with polarity.
    sign = _polarity_sign(spec["polarity"])
    pos_hits = pos_total = 0
    for s in spec.get("with", []):
        snap = market.get(s)
        if snap is None: continue
        pos_total += 1
        # Direction we want depends on whether the symbol is "with" the thesis.
        if (snap.ret_5d * sign) > 0: pos_hits += 1
    confirm = round(100 * pos_hits / max(1, pos_total))

    neg_hits = neg_total = 0
    for s in spec.get("against", []):
        snap = market.get(s)
        if snap is None: continue
        neg_total += 1
        # `against` symbols agree with the thesis when they move the wrong way.
        if (snap.ret_5d * sign) < 0: neg_hits += 1
    # dissent = 100 - confirm-style for `against` working correctly + flow_skew dissent
    dissent = round(100 - 100 * neg_hits / max(1, neg_total)) if neg_total else (100 - confirm)
    dissent = max(0, min(100, dissent))

    # Tier
    if strength >= 75 and trend7 >= -2:
        tier = "dominant"
    elif velocity >= 0.6:
        tier = "rising"
    elif velocity <= -0.6:
        tier = "fading"
    elif strength <= 35:
        tier = "latent"
    else:
        tier = "rising" if trend7 >= 0 else "fading"

    reads = []
    if components["news"] > 0.6:
        reads.append(f"{spec['name']}: news flow tilted positive (score {components['news']:.2f}).")
    if components["price"] < 0.4:
        reads.append(f"{spec['name']}: price action not confirming (score {components['price']:.2f}).")
    if components["flow"] > 0.65:
        reads.append(f"{spec['name']}: options flow leaning into the thesis.")
    if components["macro"] < 0.4:
        reads.append(f"{spec['name']}: macro backdrop hostile — {macro.ten_year_yield}% 10y, vix {macro.vix}.")

    return ScoredNarrative(
        spec=spec, components={k: round(v, 3) for k, v in components.items()},
        strength=strength, trend7=trend7, velocity=velocity,
        confirm=confirm, dissent=dissent,
        sparkline=sparkline, tier=tier, reads=reads,
    )


# ============================================================
#  Contradiction matrix
# ============================================================

def matrix_cell(narr: ScoredNarrative, signal: dict, macro: MacroSnapshot,
                market: Dict[str, MarketSnapshot], flow: Dict[str, FlowSnapshot]) -> dict:
    """
    For each (narrative, signal) decide ok / watch / stress with severity & note.
    The function reads:
      - vol:    vix vs vix3m, plus realized of the narrative's basket
      - brd:    macro.breadth + breadth of `with` returns
      - crd:    macro.credit_spread vs midpoint
      - rates:  macro.ten_year_yield vs midpoint, sign-aware
      - fx:     macro.dxy vs midpoint, sign-aware
      - flow:   macro.retail_skew + cp_skew of the basket
    """
    sid = signal["id"]
    sign = _polarity_sign(narr.spec["polarity"])

    state, sev, note = "watch", 0.5, "—"

    if sid == "vol":
        term = macro.vix - macro.vix3m   # > 0 means inverted (stress)
        if term > 1:
            state, sev = "stress", min(1.0, 0.55 + term * 0.07)
            note = f"VIX/VIX3M inverted ({term:+.2f}); tail bid building."
        elif term > 0:
            state, sev = "watch", 0.5 + term * 0.15
            note = "Term structure flattening — stress not yet, but compressing."
        else:
            state, sev = "ok", max(0.1, 0.4 + term * 0.05)
            note = "Term structure in contango — equity vol regime calm."

    elif sid == "brd":
        rets = [market[s].ret_5d for s in narr.spec.get("with", []) if s in market]
        cohesion = (1 - statistics.pstdev(rets)) if len(rets) >= 2 else 1
        breadth = macro.breadth
        if breadth < -0.1 and cohesion < 0.0:
            state, sev = "stress", 0.7 + min(0.25, abs(breadth))
            note = f"Index breadth weak ({breadth:+.2f}); narrative basket dispersed."
        elif breadth < 0.05:
            state, sev = "watch", 0.5
            note = f"Breadth thinning ({breadth:+.2f}); narrative carried by leaders."
        else:
            state, sev = "ok", max(0.15, 0.45 - breadth)
            note = "Breadth confirms — broader participation behind the thesis."

    elif sid == "crd":
        cs = macro.credit_spread
        if cs > 360:
            state, sev = "stress", min(0.95, (cs - 320) / 80)
            note = f"HY OAS at {cs:.0f}bp — credit not endorsing the risk read."
        elif cs > 320:
            state, sev = "watch", 0.45 + (cs - 320) / 200
            note = f"HY OAS {cs:.0f}bp — credit balancing on the edge."
        else:
            state, sev = "ok", max(0.15, (cs - 280) / 200)
            note = f"HY OAS tight at {cs:.0f}bp — credit consistent with thesis."

    elif sid == "rates":
        # narrative.macroFit guides what the narrative WANTS rates to do
        want = narr.spec.get("macroFit", {}).get("ten_year_yield", 0)
        y = macro.ten_year_yield
        gap = (y - 4.3) * (1 if want >= 0 else -1) if want != 0 else -abs(y - 4.3)
        if gap < -0.25:
            state, sev = "stress", min(0.95, 0.55 + abs(gap) * 0.4)
            note = f"10y at {y:.2f}% conflicts with thesis directional preference."
        elif gap < 0:
            state, sev = "watch", 0.45 + abs(gap) * 0.4
            note = f"10y at {y:.2f}% — rates not quite confirming."
        else:
            state, sev = "ok", max(0.15, 0.4 - gap * 0.2)
            note = f"10y at {y:.2f}% — rates aligned with thesis."

    elif sid == "fx":
        want = narr.spec.get("macroFit", {}).get("dxy", 0)
        d = macro.dxy
        gap = (d - 104) * (1 if want >= 0 else -1) if want != 0 else -abs(d - 104)
        if gap < -1.5:
            state, sev = "stress", min(0.9, 0.55 + abs(gap) * 0.05)
            note = f"DXY at {d:.2f} pushing against the thesis."
        elif gap < 0:
            state, sev = "watch", 0.45
            note = f"DXY at {d:.2f} — FX read mildly off-thesis."
        else:
            state, sev = "ok", max(0.15, 0.45 - gap * 0.05)
            note = f"DXY at {d:.2f} — FX consistent with thesis."

    elif sid == "flow":
        rs = macro.retail_skew
        cp_skews = [flow[s].cp_skew for s in narr.spec.get("with", []) if s in flow]
        avg_skew = statistics.fmean(cp_skews) if cp_skews else 0
        # If thesis wants long-equity flow but retail skew detached from
        # institutional flow, that's stress.
        detachment = abs(rs - avg_skew)
        if detachment > 0.4:
            state, sev = "stress", min(0.9, 0.55 + detachment * 0.5)
            note = f"Retail skew {rs:+.2f} vs basket flow {avg_skew:+.2f} — detachment signature."
        elif detachment > 0.2:
            state, sev = "watch", 0.45 + detachment
            note = f"Flow alignment partial — retail and dealers diverging."
        else:
            state, sev = "ok", 0.3
            note = f"Retail and dealer flow aligned (skew {rs:+.2f})."

    return {"state": state, "sev": round(sev, 2), "note": note}


# ============================================================
#  Cross-asset confirmation
# ============================================================

def crossasset_for(narr: ScoredNarrative, defs: List[dict],
                   market: Dict[str, MarketSnapshot]) -> List[dict]:
    """
    For each major asset, decide how strongly it confirms / diverges vs
    the dominant narrative, given direction of return and the narrative's polarity.
    """
    sign = _polarity_sign(narr.spec["polarity"])
    out = []
    for d in defs:
        snap = market.get(d["symbol"])
        ret_used = snap.ret_5d if snap else 0
        # Map the signed return to a confirmation amount in [0, 1].
        # ret_5d of +2% with sign=+1 → ~0.8 confirm; -2% → ~0.8 diverge.
        z = max(-3, min(3, ret_used * sign * 30))
        confirm = max(0.0, min(0.92, 0.5 + z * 0.13))
        diverge = max(0.0, min(0.85, 0.5 - z * 0.13))
        # Inject a deterministic per-asset note.
        note = build_crossasset_note(d, narr, snap, sign)
        out.append({
            "id": d["id"], "label": d["label"], "cls": d["cls"],
            "confirm": round(confirm, 2), "diverge": round(diverge, 2),
            "note": note
        })
    return out

def build_crossasset_note(asset: dict, narr: ScoredNarrative, snap, sign: int) -> str:
    if not snap:
        return f"{asset['label']}: no market data; cannot confirm."
    direction = "up" if snap.ret_5d > 0 else "down"
    pct = snap.ret_5d * 100
    if (snap.ret_5d * sign) > 0.005:
        return f"{asset['label']} {direction} {pct:+.1f}% (5d) — confirming the thesis."
    if (snap.ret_5d * sign) < -0.005:
        return f"{asset['label']} {direction} {pct:+.1f}% (5d) — diverging from the thesis."
    return f"{asset['label']} flat ({pct:+.1f}% 5d) — neutral read."


# ============================================================
#  Psychology
# ============================================================

def psychology(macro: MacroSnapshot, scored: List[ScoredNarrative]) -> List[dict]:
    """Composite psychology dimensions + a one-line caption per cell."""
    fg = max(0, min(100, int(60 + (macro.breadth - macro.vix / 100 + 0.2) * 100)))
    conviction = max(0, min(100, int(60 + statistics.fmean(s.confirm for s in scored) * 0.2 - 20)))
    crowding = max(0, min(100, int(50 + macro.retail_skew * 80 + 5)))
    complacency = max(0, min(100, int(55 + (17 - macro.vix) * 4)))
    recency = max(0, min(100, int(55 + macro.breadth * 60)))
    hindsight = max(0, min(100, int(50 - (macro.vix - 17) * 2)))
    dispersion = max(0, min(100, int(55 - statistics.pstdev([s.strength for s in scored]) / 2)))
    velocity_idx = max(0, min(100, int(50 + statistics.fmean(s.velocity for s in scored) * 18)))

    def captionate(label, value):
        if "Fear" in label:
            if value > 70: return "Greed-side; crowding rising — fragility risk."
            if value < 30: return "Fear-side; bearish sentiment crowded."
            return "Mid-range; neither side dominant."
        if "Conviction" in label:
            return "Conviction softening as narrative dispersion widens." if value < 60 else "Conviction healthy across the board."
        if "Crowding" in label:
            return "Top-decile crowding in leadership basket." if value > 65 else "Crowding moderate; positioning balanced."
        if "Complacency" in label:
            return "Implied skew compressed; tails priced cheap." if value > 60 else "Tails being respected — normal hedging."
        if "Recency" in label:
            return "Trailing returns extrapolated heavily into surveys." if value > 60 else "Recency bias tame."
        if "Hindsight" in label:
            return "Soft-landing being narrated as obvious in retrospect." if value > 50 else "Hindsight bias muted."
        if "Dispersion" in label:
            return "Bears thinning; lower dispersion = fragility." if value < 50 else "Healthy dispersion — diverse views."
        return "Net narrative shifts accelerating week-over-week." if value > 55 else "Narrative landscape stable."

    cells = [
        {"id": "fg",        "label": "Fear / Greed",         "value": fg,            "color": "warm",  "dir": +1 if fg > 55 else -1},
        {"id": "conv",      "label": "Conviction",           "value": conviction,    "color": "cool",  "dir": -1 if conviction < 60 else +1},
        {"id": "crowd",     "label": "Crowding",             "value": crowding,      "color": "hot",   "dir": +1 if crowding > 60 else 0},
        {"id": "compl",     "label": "Complacency",          "value": complacency,   "color": "warm",  "dir": +1 if complacency > 55 else -1},
        {"id": "recency",   "label": "Recency Bias",         "value": recency,       "color": "warm",  "dir": +1 if recency > 50 else 0},
        {"id": "hindsight", "label": "Hindsight Bias",       "value": hindsight,     "color": "cool",  "dir": 0},
        {"id": "disp",      "label": "Sentiment Dispersion", "value": dispersion,    "color": "cool",  "dir": -1 if dispersion < 50 else +1},
        {"id": "vela",      "label": "Velocity (Δ)",         "value": velocity_idx,  "color": "warm",  "dir": +1 if velocity_idx > 50 else -1},
    ]
    for c in cells:
        c["caption"] = captionate(c["label"], c["value"])
    return cells


# ============================================================
#  Regime
# ============================================================

def classify_regime(macro: MacroSnapshot, scored: List[ScoredNarrative]) -> dict:
    """A small rule-based regime classifier. Returns {primary, secondary, conviction, ageWeeks, …}."""
    # Heuristics over macro + composite read.
    risk_score = max(-1, min(1, (macro.breadth - (macro.vix - 17) / 12 + 0.1)))
    inflation_pressure = (macro.cpi_yoy - 2.6) * 1.4 + (macro.term_premium / 60)
    growth = macro.industrial_production
    tight = macro.fed_funds > 4.5

    if growth < 0 and inflation_pressure > 0.6:
        primary = "Stagflation"
        secondary = "Cost-push · margin compression"
    elif growth < 0:
        primary = "Recession Onset"
        secondary = "Risk-off · credit widening"
    elif inflation_pressure > 0.8 and risk_score < 0.1:
        primary = "Late-cycle · Reflation pressure"
        secondary = "Sticky inflation · stagflation watch"
    elif risk_score > 0.4 and inflation_pressure < 0.0:
        primary = "Soft Landing"
        secondary = "Disinflation · risk-on consensus"
    elif tight and inflation_pressure > 0.0:
        primary = "Late-cycle expansion"
        secondary = "Disinflationary tilt · fiscal overhang"
    else:
        primary = "Late-cycle expansion"
        secondary = "Mixed signals · transition risk"

    consensus = round(statistics.fmean(s.confirm for s in scored))
    conviction = max(20, min(95, int(60 + (risk_score * 20) - abs(inflation_pressure) * 8)))
    transition_prob = round(max(0.05, min(0.85,
        0.25 + abs(inflation_pressure) * 0.2 + (0.4 if growth < 0.5 else 0))), 2)

    return {
        "primary": primary,
        "secondary": secondary,
        "riskOn": round(risk_score, 2),
        "consensus": consensus,
        "conviction": conviction,
        "ageWeeks": 14,
        "transitionProb": transition_prob,
        "asOf": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# ============================================================
#  Regime history
# ============================================================

def regime_history(today: date = None) -> List[dict]:
    """A synthesized 18-month regime history; deterministic per-day."""
    today = today or date.today()
    rng = seeded_rng("regime_history", today.isoformat())
    timeline = [
        {"id": "early-cycle-reflation", "name": "Early-cycle Reflation",
         "polarity": "bullish-risk",
         "startWeeksAgo": 78, "endWeeksAgo": 64, "peakStrength": 72,
         "transitionReason": "Fed cuts run out of room; rates floor reasserted."},
        {"id": "soft-landing-1", "name": "Soft Landing v1",
         "polarity": "bullish-risk",
         "startWeeksAgo": 64, "endWeeksAgo": 41, "peakStrength": 78,
         "transitionReason": "Sticky services CPI cracks the disinflation script."},
        {"id": "higher-for-longer-1", "name": "Higher-for-Longer",
         "polarity": "bearish-duration",
         "startWeeksAgo": 41, "endWeeksAgo": 26, "peakStrength": 67,
         "transitionReason": "Labor cools; Powell pivots dovish."},
        {"id": "soft-landing-2", "name": "Soft Landing v2",
         "polarity": "bullish-risk",
         "startWeeksAgo": 26, "endWeeksAgo": 14, "peakStrength": 71,
         "transitionReason": "Term-premium re-emergence dents pricing of cuts."},
        {"id": "late-cycle-current", "name": "Late-cycle · Disinflationary tilt",
         "polarity": "neutral",
         "startWeeksAgo": 14, "endWeeksAgo": 0, "peakStrength": 73,
         "transitionReason": "Current regime."},
    ]
    # Add small per-run noise so peakStrength feels alive, not frozen.
    for r in timeline:
        r["peakStrength"] = max(40, min(92, r["peakStrength"] + int(rng.gauss(0, 2))))
    return timeline


# ============================================================
#  Dependency graph
# ============================================================

def dependency_graph(spec: dict, scored_by_id: Dict[str, ScoredNarrative]) -> dict:
    """
    Build node + edge data for the dependency graph view.
    Node coordinates are pre-computed from a small force-directed-ish layout
    so the frontend doesn't need a layout solver.
    """
    nids = [n["id"] for n in spec["narratives"]]
    n = len(nids)
    nodes = []
    # Distribute on a circle, with strong narratives pulled slightly toward center.
    for i, nid in enumerate(nids):
        ang = (i / n) * math.tau - math.pi / 2
        sn = scored_by_id.get(nid)
        strength = sn.strength if sn else 50
        radius = 1.0 - (strength - 50) / 220   # 0.55..1.0
        x = math.cos(ang) * radius
        y = math.sin(ang) * radius
        nodes.append({
            "id": nid,
            "name": next(s["name"] for s in spec["narratives"] if s["id"] == nid),
            "x": round(x, 3), "y": round(y, 3),
            "strength": strength,
            "tier": sn.tier if sn else "latent",
        })
    edges = []
    for e in spec.get("dependencies", []):
        # Hide edges where either side is very weak — keeps the graph readable.
        a = scored_by_id.get(e["from"]); b = scored_by_id.get(e["to"])
        if a and b and (a.strength + b.strength) > 80:
            edges.append({
                "from": e["from"], "to": e["to"],
                "type": e["type"],
                "strength": e["strength"],
                "note": e["note"],
            })
    return {"nodes": nodes, "edges": edges}


# ============================================================
#  Backtest events
# ============================================================

CANNED_BACKTEST = [
    {"id": "bt-2024-08", "detectedWeeksAgo": 90, "narrative": "Soft Landing v1", "signal": "Vol term structure",
     "severityAtDetection": 0.78, "resolutionDays": 21, "regimeBreak": True,
     "marketReactionPct": -6.4, "lesson": "VIX/VIX3M inversion on rising index → 14d drawdown median."},
    {"id": "bt-2024-11", "detectedWeeksAgo": 78, "narrative": "Soft Landing v1", "signal": "Credit spreads",
     "severityAtDetection": 0.55, "resolutionDays": 38, "regimeBreak": False,
     "marketReactionPct": +1.1, "lesson": "Single-signal contradictions resolve benignly ~62% of the time."},
    {"id": "bt-2025-02", "detectedWeeksAgo": 65, "narrative": "AI Supercycle", "signal": "Equity breadth",
     "severityAtDetection": 0.81, "resolutionDays": 45, "regimeBreak": False,
     "marketReactionPct": -3.2, "lesson": "Concentration risk leads, not lags — fade strength when breadth diverges 4w."},
    {"id": "bt-2025-05", "detectedWeeksAgo": 52, "narrative": "Higher-for-Longer", "signal": "Rates / curve",
     "severityAtDetection": 0.74, "resolutionDays": 16, "regimeBreak": True,
     "marketReactionPct": -4.8, "lesson": "Rates-led contradictions resolve fastest; 14–18d typical."},
    {"id": "bt-2025-07", "detectedWeeksAgo": 44, "narrative": "Reshoring", "signal": "FX / DXY",
     "severityAtDetection": 0.45, "resolutionDays": 60, "regimeBreak": False,
     "marketReactionPct": -0.4, "lesson": "FX divergences alone are weak triggers."},
    {"id": "bt-2025-10", "detectedWeeksAgo": 31, "narrative": "Soft Landing v2", "signal": "Vol term structure",
     "severityAtDetection": 0.69, "resolutionDays": 25, "regimeBreak": True,
     "marketReactionPct": -5.1, "lesson": "Repeat of 2024-08 signature — vol-term-structure is the highest-fidelity early warning."},
    {"id": "bt-2025-12", "detectedWeeksAgo": 22, "narrative": "Bond Vigilantes", "signal": "Rates / curve",
     "severityAtDetection": 0.82, "resolutionDays": 12, "regimeBreak": True,
     "marketReactionPct": -3.9, "lesson": "Term-premium repricing → multiple compression in long-duration baskets."},
    {"id": "bt-2026-02", "detectedWeeksAgo": 12, "narrative": "AI Supercycle", "signal": "Retail vs dealer flow",
     "severityAtDetection": 0.72, "resolutionDays": 18, "regimeBreak": False,
     "marketReactionPct": -2.7, "lesson": "Retail/dealer flow detachment → mean-reversion over 2–3w."},
    {"id": "bt-2026-04", "detectedWeeksAgo": 4,  "narrative": "Soft Landing v2", "signal": "Equity breadth",
     "severityAtDetection": 0.58, "resolutionDays": None, "regimeBreak": None,
     "marketReactionPct": None, "lesson": "Open. Severity rising; mirrors 2025-02 progression."},
]

def backtest_block() -> dict:
    closed = [e for e in CANNED_BACKTEST if e["resolutionDays"] is not None]
    breaks = [e for e in closed if e["regimeBreak"]]
    avg_lead = statistics.fmean(e["resolutionDays"] for e in closed)
    avg_react = statistics.fmean(e["marketReactionPct"] for e in closed)
    return {
        "events": CANNED_BACKTEST,
        "stats": {
            "events": len(CANNED_BACKTEST),
            "regimeBreakHitRate": round(100 * len(breaks) / max(1, len(closed))),
            "avgLeadDays": round(avg_lead, 1),
            "avgReactionPct": round(avg_react, 2),
        }
    }


# ============================================================
#  Insight feed
# ============================================================

def insights(scored: List[ScoredNarrative], macro: MacroSnapshot,
             matrix: Dict[str, Dict[str, dict]]) -> List[dict]:
    """Build a small, deduplicated list of plain-English observations."""
    out = []
    by_strength = sorted(scored, key=lambda s: s.strength, reverse=True)
    dom = by_strength[0]
    fade_candidates = [s for s in by_strength if s.velocity < -0.5]
    rise_candidates = [s for s in by_strength if s.velocity > 0.5]

    if dom.confirm < 60:
        out.append({"tag": "DIVERGENCE", "ts": "-7m",
                    "body": f"{dom.spec['name']} narrative weakening despite headline strength — confirmation just {dom.confirm}%."})
    if macro.vix < macro.vix3m - 1:
        out.append({"tag": "REGIME", "ts": "-21m",
                    "body": "Volatility term structure inverted — equity calm masking tail bid."})
    if any(c["state"] == "stress" for n in matrix.values() for c in n.values()):
        contradictions = sum(1 for n in matrix.values() for c in n.values() if c["state"] == "stress")
        out.append({"tag": "CONTRADICTION", "ts": "-12m",
                    "body": f"{contradictions} active narrative × signal contradictions — broadest in 6 weeks."})
    if rise_candidates:
        n = rise_candidates[0]
        out.append({"tag": "CONFIRMATION", "ts": "-34m",
                    "body": f"{n.spec['name']} thesis gaining: velocity {n.velocity:+.2f}σ on {n.confirm}% confirmation."})
    if fade_candidates:
        n = fade_candidates[0]
        out.append({"tag": "FLOW", "ts": "-26m",
                    "body": f"{n.spec['name']} fading: 7d trend {n.trend7:+.1f}, dissent {n.dissent}%."})
    if macro.breadth < 0:
        out.append({"tag": "CROWDING", "ts": "-58m",
                    "body": f"Breadth weakening ({macro.breadth:+.2f}) — leadership carrying the index."})
    if macro.term_premium > 25:
        out.append({"tag": "VOLATILITY", "ts": "-2h",
                    "body": f"Term premium at {macro.term_premium:.0f}bp — bond vol leading equity vol."})
    if dom.spec["id"] == "ai-supercycle" and dom.components.get("price", 1) < 0.5:
        out.append({"tag": "DIVERGENCE", "ts": "-1h",
                    "body": "AI supercycle headlines positive while basket price action diverges — classic detachment signature."})

    # Always include a few canned framing reads for variety
    out.extend([
        {"tag": "REGIME", "ts": "-42m",
         "body": "Higher-for-longer regaining strength as long-end yields refuse to confirm cuts."},
        {"tag": "CHINA",  "ts": "-1h",
         "body": "China stimulus narrative fading: foreign investors net sellers despite property white-list headlines."},
    ])
    # Dedup by body
    seen, uniq = set(), []
    for o in out:
        if o["body"] in seen: continue
        seen.add(o["body"]); uniq.append(o)
    return uniq[:10]


# ============================================================
#  Snapshot assembly
# ============================================================

def build_snapshot(spec: dict) -> dict:
    today = date.today()
    news = generate_news(spec["narratives"], today=today)

    # Symbols we need flow + market data for
    narr_syms = [s for n in spec["narratives"] for s in n.get("with", []) + n.get("against", [])]
    ca_syms = [d["symbol"] for d in spec["crossAsset"]]
    syms = sorted(set(narr_syms + ca_syms))
    flow = generate_flow(syms, today=today)
    market = generate_market(syms, today=today)
    macro = generate_macro(today=today)

    scored = [score_narrative(n, news, flow, market, macro) for n in spec["narratives"]]
    by_id = {s.spec["id"]: s for s in scored}
    dom = max(scored, key=lambda s: s.strength)

    matrix: Dict[str, Dict[str, dict]] = {}
    for s in scored:
        matrix[s.spec["id"]] = {sig["id"]: matrix_cell(s, sig, macro, market, flow)
                                for sig in spec["signals"]}

    snapshot = {
        "schemaVersion": 1,
        "source": "scoring-pipeline",
        "REGIME": classify_regime(macro, scored),
        "REGIME_HISTORY": regime_history(today),
        "NARRATIVES": [
            {
                "id": s.spec["id"], "name": s.spec["name"], "tagline": s.spec["tagline"],
                "polarity": s.spec["polarity"], "ageWeeks": s.spec["ageWeeks"],
                "drivers": s.spec.get("drivers", []),
                "with": s.spec.get("with", []), "against": s.spec.get("against", []),
                "strength": s.strength, "trend7": s.trend7, "velocity": s.velocity,
                "confirm": s.confirm, "dissent": s.dissent,
                "tier": s.tier, "components": s.components,
                "sparkline": s.sparkline,
            } for s in scored
        ],
        "SIGNALS": spec["signals"],
        "MATRIX": matrix,
        "CROSSASSET": crossasset_for(dom, spec["crossAsset"], market),
        "PSYCHOLOGY": psychology(macro, scored),
        "INSIGHTS": insights(scored, macro, matrix),
        "DEPENDENCIES": dependency_graph(spec, by_id),
        "BACKTEST": backtest_block(),
        "MACRO_SNAPSHOT": {
            "ten_year_yield": macro.ten_year_yield, "real_rates": macro.real_rates,
            "dxy": macro.dxy, "vix": macro.vix, "vix3m": macro.vix3m, "move": macro.move,
            "fed_funds": macro.fed_funds, "cpi_yoy": macro.cpi_yoy,
            "credit_spread": macro.credit_spread, "term_premium": macro.term_premium,
            "breadth": macro.breadth, "retail_skew": macro.retail_skew,
        }
    }
    return snapshot


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output JSON path")
    p.add_argument("--print", dest="print_summary", action="store_true",
                   help="Print summary to stdout instead of writing")
    args = p.parse_args()

    spec = json.loads(SPEC_PATH.read_text())
    snap = build_snapshot(spec)

    if args.print_summary:
        print(f"Regime: {snap['REGIME']['primary']} · {snap['REGIME']['secondary']}")
        print(f"        consensus {snap['REGIME']['consensus']}  conviction {snap['REGIME']['conviction']}  riskOn {snap['REGIME']['riskOn']}")
        print(f"Narratives ({len(snap['NARRATIVES'])}):")
        for n in sorted(snap["NARRATIVES"], key=lambda x: x["strength"], reverse=True):
            print(f"  {n['strength']:>5.1f}  {n['name']:<28}  tier={n['tier']:<9} velocity={n['velocity']:+.2f}σ trend7={n['trend7']:+.1f}")
        n_stress = sum(1 for nm in snap["MATRIX"].values() for c in nm.values() if c["state"] == "stress")
        n_watch = sum(1 for nm in snap["MATRIX"].values() for c in nm.values() if c["state"] == "watch")
        print(f"Matrix: {n_stress} stress · {n_watch} watch · {len(snap['MATRIX']) * len(snap['SIGNALS'])} cells total")
        print(f"Insights: {len(snap['INSIGHTS'])}")
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snap, indent=2))
    print(f"Wrote {args.out} ({args.out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
