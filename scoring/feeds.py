"""
Mock data feeds for the narrative scoring pipeline.

Every adapter exposes the same simple shape so the scorer doesn't care
whether it's reading from a mock file or a live vendor:

    News  : list[NewsItem]
    Flow  : dict[symbol -> FlowSnapshot]
    Market: dict[symbol -> MarketSnapshot]
    Macro : MacroSnapshot

To swap in a real feed, implement the same protocol against Polygon /
Benzinga / FRED / etc. and inject it into Pipeline.run().

The mocks are deterministic per-day: same date in → same numbers out.
That gives stable demos and reproducible tests without freezing the
prototype into one hard-coded screenshot.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
import hashlib
import math
import random


# ---------- Determinism ----------------------------------------------

def seeded_rng(*tokens) -> random.Random:
    """Deterministic RNG keyed on a tuple of identifiers + today's date."""
    key = "|".join(str(t) for t in tokens)
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))


# ---------- News ------------------------------------------------------

@dataclass
class NewsItem:
    ts: datetime
    headline: str
    tickers: List[str]
    topics: List[str]            # e.g. ["ai", "capex"]
    sentiment: float             # [-1, +1]
    source: str

# Topic taxonomy used by the mock generator. In production this is
# either an LLM event extractor or a curated keyword graph.
TOPIC_BANK = {
    "ai-supercycle":     ["ai", "capex", "datacenter", "gpu", "hyperscaler"],
    "soft-landing":      ["disinflation", "labor", "wages", "productivity", "fed"],
    "higher-for-longer": ["sticky", "fiscal", "yields", "term-premium", "auction"],
    "reshoring":         ["chips", "ira", "industrial", "manufacturing", "defense"],
    "energy-stress":     ["power", "grid", "uranium", "transmission", "datacenter"],
    "bond-vigilantes":   ["auction", "tail", "term-premium", "supply", "fiscal"],
    "dxy-wrecking":      ["dollar", "carry", "em", "fx"],
    "china-stimulus":    ["pboc", "property", "rrr", "stimulus", "white-list"],
    "geopolitical":      ["strait", "gulf", "shipping", "defense", "tail-risk"],
    "crypto-rerating":   ["btc", "etf", "halving", "sovereign", "reserve"],
}

HEADLINE_TEMPLATES = {
    "positive": [
        "{topic_h}: data prints above consensus; {tag} thesis gains traction",
        "Street raises 2026 estimates as {topic_h} momentum compounds",
        "Survey: institutional positioning rotates into {topic_h} basket",
        "Earnings call commentary corroborates {topic_h} narrative",
        "ETF flows: {tag} basket sees sixth consecutive week of inflows",
    ],
    "negative": [
        "Cracks emerge in {topic_h} story as breadth narrows",
        "Sell-side downgrades: {topic_h} thesis 'priced for perfection'",
        "Hedge fund letter flags {tag} as crowded and reflexive",
        "Forward guidance softens — {topic_h} losing forward-look support",
        "Realized data undershoots; {topic_h} repriced lower",
    ],
    "neutral": [
        "{topic_h}: positioning balanced; awaiting next macro print",
        "Mixed signals across {tag} sub-sectors",
    ],
}

def generate_news(narratives: List[dict], n_items: int = 60, today: Optional[date] = None) -> List[NewsItem]:
    today = today or date.today()
    items: List[NewsItem] = []
    for n in narratives:
        rng = seeded_rng("news", n["id"], today.isoformat())
        # how many headlines map to this narrative
        count = max(2, int(rng.gauss(n_items / len(narratives), 1.5)))
        topics = TOPIC_BANK.get(n["id"], [])
        # sentiment bias by recency / status
        # A narrative whose tier we don't know yet — use a deterministic drift.
        bias = rng.uniform(-0.15, 0.25)
        for _ in range(count):
            polarity = rng.choices(["positive", "negative", "neutral"],
                                   weights=[0.5 + bias, 0.35 - bias / 2, 0.15], k=1)[0]
            template = rng.choice(HEADLINE_TEMPLATES[polarity])
            sent = {"positive": rng.uniform(0.3, 0.85),
                    "negative": rng.uniform(-0.85, -0.3),
                    "neutral":  rng.uniform(-0.15, 0.15)}[polarity]
            headline = template.format(
                topic_h=rng.choice(topics).title() if topics else n["name"],
                tag=n["name"]
            )
            ts = datetime.combine(today, datetime.min.time()) - timedelta(hours=rng.randint(0, 168))
            items.append(NewsItem(
                ts=ts, headline=headline,
                tickers=n.get("with", [])[:2],
                topics=topics + [n["id"]],
                sentiment=sent,
                source=rng.choice(["BZ", "WSJ", "Bloomberg", "Reuters", "FT"])
            ))
    items.sort(key=lambda x: x.ts, reverse=True)
    return items


# ---------- Options flow ---------------------------------------------

@dataclass
class FlowSnapshot:
    symbol: str
    call_premium_usd: float
    put_premium_usd: float
    call_oi: int
    put_oi: int
    sweep_count: int
    block_premium_usd: float
    iv_rank: float               # [0, 100]

    @property
    def net_premium(self) -> float:
        return self.call_premium_usd - self.put_premium_usd

    @property
    def cp_skew(self) -> float:
        total = self.call_premium_usd + self.put_premium_usd
        return 0.0 if total == 0 else (self.call_premium_usd - self.put_premium_usd) / total

def generate_flow(symbols: List[str], today: Optional[date] = None) -> Dict[str, FlowSnapshot]:
    today = today or date.today()
    out: Dict[str, FlowSnapshot] = {}
    for sym in symbols:
        rng = seeded_rng("flow", sym, today.isoformat())
        scale = rng.uniform(2e6, 4e7)
        skew = rng.uniform(-0.4, 0.6)         # positive = call-heavy
        out[sym] = FlowSnapshot(
            symbol=sym,
            call_premium_usd=scale * (1 + skew) / 2,
            put_premium_usd=scale * (1 - skew) / 2,
            call_oi=int(rng.uniform(8e4, 8e5)),
            put_oi=int(rng.uniform(4e4, 6e5)),
            sweep_count=int(rng.uniform(2, 80)),
            block_premium_usd=scale * rng.uniform(0.05, 0.4),
            iv_rank=round(rng.uniform(15, 90), 1),
        )
    return out


# ---------- Market ----------------------------------------------------

@dataclass
class MarketSnapshot:
    symbol: str
    last: float
    ret_1d: float
    ret_5d: float
    ret_20d: float
    realized_vol_20d: float      # annualized
    z_volume_20d: float          # current vol vs 20d avg
    breadth_advdec: float        # for index proxies; -1..+1

def generate_market(symbols: List[str], today: Optional[date] = None) -> Dict[str, MarketSnapshot]:
    today = today or date.today()
    out: Dict[str, MarketSnapshot] = {}
    for sym in symbols:
        rng = seeded_rng("market", sym, today.isoformat())
        last = rng.uniform(15, 600)
        ret1 = rng.gauss(0.001, 0.012)
        ret5 = rng.gauss(0.005, 0.025)
        ret20 = rng.gauss(0.015, 0.05)
        out[sym] = MarketSnapshot(
            symbol=sym,
            last=round(last, 2),
            ret_1d=round(ret1, 4),
            ret_5d=round(ret5, 4),
            ret_20d=round(ret20, 4),
            realized_vol_20d=round(abs(rng.gauss(0.18, 0.08)), 3),
            z_volume_20d=round(rng.gauss(0, 1.1), 2),
            breadth_advdec=round(rng.uniform(-0.6, 0.7), 2)
        )
    return out


# ---------- Macro -----------------------------------------------------

@dataclass
class MacroSnapshot:
    ten_year_yield: float        # %
    real_rates: float            # 10y TIPS, %
    dxy: float
    vix: float
    vix3m: float
    move: float                  # bond vol index, bp
    fed_funds: float
    cpi_yoy: float
    industrial_production: float # YoY %
    credit_spread: float         # HY OAS, bp
    term_premium: float          # bp
    breadth: float               # SPX cumulative AD line z, -1..+1
    retail_skew: float           # call/put retail skew, -1..+1

def generate_macro(today: Optional[date] = None) -> MacroSnapshot:
    today = today or date.today()
    rng = seeded_rng("macro", today.isoformat())
    return MacroSnapshot(
        ten_year_yield=round(rng.uniform(3.9, 4.7), 2),
        real_rates=round(rng.uniform(1.6, 2.3), 2),
        dxy=round(rng.uniform(101, 107), 2),
        vix=round(rng.uniform(13, 22), 2),
        vix3m=round(rng.uniform(15, 21), 2),
        move=round(rng.uniform(95, 145), 1),
        fed_funds=round(rng.uniform(4.25, 5.25), 2),
        cpi_yoy=round(rng.uniform(2.4, 3.4), 2),
        industrial_production=round(rng.uniform(-0.5, 2.5), 2),
        credit_spread=round(rng.uniform(285, 380), 1),
        term_premium=round(rng.uniform(-25, 55), 1),
        breadth=round(rng.uniform(-0.4, 0.5), 2),
        retail_skew=round(rng.uniform(-0.2, 0.55), 2),
    )


# ---------- History (synthetic) ---------------------------------------

def generate_strength_history(narrative_id: str, target: float, today: Optional[date] = None,
                              days: int = 14) -> List[float]:
    """
    Build a 14-day strength curve that lands at `target` today.
    The walk uses the narrative id as a seed so rerunning the pipeline
    produces a coherent history rather than a fresh random walk each call.
    """
    today = today or date.today()
    rng = seeded_rng("hist", narrative_id, today.isoformat())
    drift = rng.uniform(-0.6, 0.6)
    series = [target]
    for _ in range(days - 1):
        prev = series[-1]
        step = rng.gauss(-drift, 1.2)
        nxt = max(20, min(95, prev - step))
        series.append(round(nxt, 1))
    series.reverse()
    # smooth so it lands cleanly at today's score
    series[-1] = target
    return [round(v, 1) for v in series]


# ---------- Demo ------------------------------------------------------

if __name__ == "__main__":
    import json, pathlib
    spec = json.loads(pathlib.Path(__file__).with_name("narratives.json").read_text())
    print(f"news: {len(generate_news(spec['narratives']))} items")
    flow = generate_flow([s for n in spec["narratives"] for s in n.get("with", [])])
    print(f"flow: {len(flow)} symbols")
    print(f"macro: {generate_macro()}")
