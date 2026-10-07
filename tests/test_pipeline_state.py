import tempfile
import unittest
from unittest.mock import patch

from execution import pipeline as pipeline_mod
from execution.pipeline import JobDiscoveryPipeline
from execution.sources.base import JobSource
from execution.sources.mock_source import MockJobSource
from execution.models import RawJobListing
from execution.state import JobStateStore, STATUS_EVALUATED, STATUS_REJECTED_PREFILTER


class _NonTechPlusMock(JobSource):
    """MockJobSource fixtures + one obvious non-tech listing."""

    @property
    def source_name(self) -> str:
        return "mock_plus"

    def fetch_jobs(self, query: str = "", limit: int = 20):
        jobs = MockJobSource().fetch_jobs(query="", limit=limit)
        jobs.append(RawJobListing(
            raw_id="nt-1", title="Kelio darbininkas", company="Keliai UAB",
            location_raw="Kaunas", description_raw="Kelių priežiūros darbai.",
            job_url="https://example.com/kelio-darbininkas", source="mock_plus",
        ))
        return jobs


class TestPipelineWithState(unittest.TestCase):

    def setUp(self):
        self.store = JobStateStore(":memory:")

    def tearDown(self):
        self.store.close()

    def _pipeline(self, **kw):
        return JobDiscoveryPipeline(sources=[_NonTechPlusMock()], state_store=self.store, **kw)

    def test_first_run_evaluates_and_prefilters(self):
        p = self._pipeline()
        evaluations, md, _ = p.run(query="")
        self.assertEqual(len(evaluations), 5)
        self.assertEqual(p.last_run_stats["prefiltered"], 1)
        self.assertEqual(p.last_run_stats["evaluated"], 5)
        self.assertEqual(p.last_run_stats["new"], 6)
        counts = self.store.status_counts()
        self.assertEqual(counts.get(STATUS_EVALUATED), 5)
        self.assertEqual(counts.get(STATUS_REJECTED_PREFILTER), 1)
        self.assertIn("Pre-filtered Listings (1)", md)
        self.assertIn("[NEW]", md)

    def test_second_run_makes_zero_evaluate_calls(self):
        first, _, first_json = self._pipeline().run(query="")

        with patch.object(pipeline_mod, "evaluate_job", wraps=pipeline_mod.evaluate_job) as spy:
            p2 = self._pipeline()
            second, md2, _ = p2.run(query="")
        self.assertEqual(spy.call_count, 0)
        self.assertEqual(p2.last_run_stats["cached"], 5)
        self.assertEqual(p2.last_run_stats["new"], 0)
        self.assertEqual(p2.last_run_stats["prefiltered"], 1)
        self.assertNotIn("[NEW]", md2)
        self.assertEqual(
            [(e.job_id, e.recommendation, e.total_score) for e in first],
            [(e.job_id, e.recommendation, e.total_score) for e in second],
        )

    def test_force_reeval_evaluates_everything_again(self):
        self._pipeline().run(query="")
        with patch.object(pipeline_mod, "evaluate_job", wraps=pipeline_mod.evaluate_job) as spy:
            p = self._pipeline(force_reeval=True)
            p.run(query="")
        self.assertEqual(spy.call_count, 5)
        self.assertEqual(p.last_run_stats["prefiltered"], 1)

    def test_report_scope_new_only_shows_fresh_evaluations(self):
        self._pipeline().run(query="")
        evaluations, _, _ = self._pipeline(report_scope="new").run(query="")
        self.assertEqual(evaluations, [])

    def test_no_prefilter_evaluates_non_tech_job(self):
        p = self._pipeline(enable_prefilter=False)
        evaluations, _, _ = p.run(query="")
        self.assertEqual(len(evaluations), 6)
        self.assertEqual(p.last_run_stats["prefiltered"], 0)

    def test_stateless_mode_matches_legacy_behaviour(self):
        with tempfile.TemporaryDirectory() as tmp:
            evaluations, md, _ = JobDiscoveryPipeline(sources=[MockJobSource()]).run(
                query="", output_dir=tmp
            )
        self.assertEqual(len(evaluations), 5)
        self.assertNotIn("[NEW]", md)
        self.assertNotIn("Pre-filtered Listings", md)

    def test_invalid_report_scope_rejected(self):
        with self.assertRaises(ValueError):
            JobDiscoveryPipeline(sources=[], report_scope="bogus")


if __name__ == "__main__":
    unittest.main()
