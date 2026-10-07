"""
Safety-net regression test: the pre-filter must never drop a job that the full
evaluator rated APPLY, CONSIDER or LOW_PRIORITY in a real pipeline run.

Fixture: tests/fixtures/eval_snapshot_2026_10_05.json (253 real listings).
Only titles are available in the snapshot, so this is the strictest setting
(no description override can rescue a blocked title).
"""
import json
import os
import unittest

from execution.prefilter import prefilter_title

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "eval_snapshot_2026_10_05.json")
KEEP = {"APPLY", "CONSIDER", "LOW_PRIORITY"}


class TestPrefilterRegression(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(FIXTURE, encoding="utf-8") as f:
            cls.snapshot = json.load(f)

    def test_snapshot_loaded(self):
        self.assertEqual(len(self.snapshot), 253)

    def test_zero_false_negatives_against_evaluator(self):
        false_negatives = [
            (j["title"], j["recommendation"], prefilter_title(j["title"]).reason)
            for j in self.snapshot
            if j["recommendation"] in KEEP and not prefilter_title(j["title"]).passed
        ]
        self.assertEqual(false_negatives, [], f"Pre-filter dropped viable jobs: {false_negatives}")

    def test_blocked_jobs_are_all_evaluator_rejects(self):
        blocked = [j for j in self.snapshot if not prefilter_title(j["title"]).passed]
        for j in blocked:
            with self.subTest(title=j["title"]):
                self.assertEqual(j["recommendation"], "REJECT")
        # Informational only - intentionally not asserted as a target.
        print(f"\n[prefilter regression] blocked {len(blocked)}/"
              f"{sum(1 for j in self.snapshot if j['recommendation'] == 'REJECT')} evaluator rejects")


if __name__ == "__main__":
    unittest.main()
