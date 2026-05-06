"""
Smoke + contract tests for the scoring pipeline.

These don't try to validate financial logic — they verify that the snapshot
shape is exactly what the frontend expects, so a refactor that breaks the
contract is caught fast. Run:

    cd scoring && python3 tests/test_pipeline.py
"""

from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path

# Make scoring/ importable when run as a script
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import build_snapshot, SPEC_PATH


class PipelineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(SPEC_PATH.read_text())
        cls.snap = build_snapshot(cls.spec)

    def test_top_level_keys(self):
        expected = {"REGIME", "REGIME_HISTORY", "NARRATIVES", "SIGNALS", "MATRIX",
                    "CROSSASSET", "PSYCHOLOGY", "INSIGHTS", "DEPENDENCIES",
                    "BACKTEST", "MACRO_SNAPSHOT", "schemaVersion", "source"}
        self.assertTrue(expected.issubset(self.snap.keys()),
                        f"Missing keys: {expected - set(self.snap.keys())}")

    def test_narrative_shape(self):
        self.assertEqual(len(self.snap["NARRATIVES"]), len(self.spec["narratives"]))
        for n in self.snap["NARRATIVES"]:
            for k in ("id","name","tagline","strength","trend7","velocity","confirm",
                      "dissent","tier","sparkline","components","drivers","with","against"):
                self.assertIn(k, n, f"Narrative missing field: {k}")
            self.assertEqual(len(n["sparkline"]), 14)
            self.assertGreaterEqual(n["strength"], 0)
            self.assertLessEqual(n["strength"], 100)
            self.assertIn(n["tier"], {"dominant", "rising", "fading", "latent", "counter"})

    def test_matrix_dimensions(self):
        narrative_ids = [n["id"] for n in self.snap["NARRATIVES"]]
        signal_ids = [s["id"] for s in self.snap["SIGNALS"]]
        self.assertEqual(set(self.snap["MATRIX"].keys()), set(narrative_ids))
        for nid, row in self.snap["MATRIX"].items():
            self.assertEqual(set(row.keys()), set(signal_ids), f"Matrix row {nid}")
            for sid, cell in row.items():
                self.assertIn(cell["state"], {"ok", "watch", "stress"})
                self.assertIsInstance(cell["sev"], (int, float))
                self.assertIsInstance(cell["note"], str)
                self.assertGreater(len(cell["note"]), 4)

    def test_crossasset_shape(self):
        self.assertGreater(len(self.snap["CROSSASSET"]), 8)
        for a in self.snap["CROSSASSET"]:
            for k in ("id", "label", "cls", "confirm", "diverge", "note"):
                self.assertIn(k, a)
            self.assertGreaterEqual(a["confirm"], 0); self.assertLessEqual(a["confirm"], 1)
            self.assertGreaterEqual(a["diverge"], 0); self.assertLessEqual(a["diverge"], 1)

    def test_psychology_cells(self):
        self.assertEqual(len(self.snap["PSYCHOLOGY"]), 8)
        for p in self.snap["PSYCHOLOGY"]:
            self.assertIn(p["color"], {"hot", "warm", "cool"})
            self.assertGreaterEqual(p["value"], 0); self.assertLessEqual(p["value"], 100)
            self.assertGreater(len(p["caption"]), 4)

    def test_dependencies_shape(self):
        deps = self.snap["DEPENDENCIES"]
        self.assertEqual(len(deps["nodes"]), len(self.spec["narratives"]))
        for n in deps["nodes"]:
            for k in ("id", "name", "x", "y", "strength", "tier"):
                self.assertIn(k, n)
        narrative_ids = {n["id"] for n in deps["nodes"]}
        for e in deps["edges"]:
            self.assertIn(e["from"], narrative_ids)
            self.assertIn(e["to"],   narrative_ids)
            self.assertIn(e["type"], {"reinforce", "oppose"})

    def test_backtest_shape(self):
        bt = self.snap["BACKTEST"]
        self.assertGreater(len(bt["events"]), 4)
        for k in ("events", "regimeBreakHitRate", "avgLeadDays", "avgReactionPct"):
            self.assertIn(k, bt["stats"])
        for e in bt["events"]:
            for k in ("id", "detectedWeeksAgo", "narrative", "signal",
                      "severityAtDetection", "regimeBreak", "lesson"):
                self.assertIn(k, e)

    def test_regime_history_ordered(self):
        hist = self.snap["REGIME_HISTORY"]
        self.assertGreater(len(hist), 2)
        # Each transition must end at or after the next one starts (timeline coherence).
        for prev, curr in zip(hist, hist[1:]):
            self.assertLessEqual(curr["startWeeksAgo"], prev["startWeeksAgo"])
            self.assertLessEqual(prev["endWeeksAgo"], prev["startWeeksAgo"])

    def test_insights_have_known_tags(self):
        known = {"DIVERGENCE","CONTRADICTION","CONFIRMATION","REGIME","FLOW",
                 "CROWDING","CHINA","VOLATILITY"}
        for i in self.snap["INSIGHTS"]:
            self.assertIn(i["tag"], known)
            self.assertGreater(len(i["body"]), 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
