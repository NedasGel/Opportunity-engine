import tempfile
import unittest
from unittest.mock import patch

from execution import pipeline as pipeline_mod
from execution.pipeline import JobDiscoveryPipeline
from execution.sources.base import JobSource
from execution.sources.mock_source import MockJobSource
from execution.models import RawJobListing, ApplicationStatus
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

    def test_pipeline_reruns_and_reevaluations_preserve_application_status_and_notes(self):
        first_evals, _, _ = self._pipeline().run(query="")
        target_job_id = first_evals[0].job_id
        second_job_id = first_evals[1].job_id

        # User tracks progress on two jobs
        self.store.update_application_status(
            target_job_id, ApplicationStatus.APPLIED, user_notes="Sent CV via LinkedIn"
        )
        self.store.update_application_status(
            second_job_id, ApplicationStatus.INTERVIEW, user_notes="Recruiter call scheduled"
        )

        # 1. Normal cached pipeline re-run preserves status and notes
        cached_evals, _, _ = self._pipeline().run(query="")
        by_id_cached = {e.job_id: e for e in cached_evals}
        self.assertEqual(by_id_cached[target_job_id].application_status, ApplicationStatus.APPLIED)
        self.assertEqual(by_id_cached[target_job_id].user_notes, "Sent CV via LinkedIn")
        self.assertEqual(by_id_cached[second_job_id].application_status, ApplicationStatus.INTERVIEW)
        self.assertEqual(by_id_cached[second_job_id].user_notes, "Recruiter call scheduled")

        # 2. Forced re-evaluation (force_reeval=True) NEVER resets status or notes
        reeval_evals, _, _ = self._pipeline(force_reeval=True).run(query="")
        by_id_reeval = {e.job_id: e for e in reeval_evals}
        self.assertEqual(by_id_reeval[target_job_id].application_status, ApplicationStatus.APPLIED)
        self.assertEqual(by_id_reeval[target_job_id].user_notes, "Sent CV via LinkedIn")
        self.assertEqual(by_id_reeval[second_job_id].application_status, ApplicationStatus.INTERVIEW)
        self.assertEqual(by_id_reeval[second_job_id].user_notes, "Recruiter call scheduled")

        # Verify database records still hold the user's status and notes
        rec1 = self.store.get(target_job_id)
        rec2 = self.store.get(second_job_id)
        self.assertEqual(rec1.application_status, "APPLIED")
        self.assertEqual(rec1.user_notes, "Sent CV via LinkedIn")
        self.assertEqual(rec2.application_status, "INTERVIEW")
        self.assertEqual(rec2.user_notes, "Recruiter call scheduled")

    def test_unseen_and_expired_jobs_marked_inactive(self):
        class _DynamicSource(JobSource):
            def __init__(self, listings):
                self._listings = listings

            @property
            def source_name(self) -> str:
                return "dyn"

            def fetch_jobs(self, query: str = "", limit: int = 20):
                return list(self._listings)

        job_a = RawJobListing(
            raw_id="a1", title="Junior AI Intern", company="Alpha",
            location_raw="Vilnius", description_raw="Python AI role for students.",
            job_url="https://example.com/a1", source="dyn",
        )
        job_b = RawJobListing(
            raw_id="b1", title="ML Intern", company="Beta",
            location_raw="Vilnius", description_raw="Machine learning internship.",
            job_url="https://example.com/b1", source="dyn",
        )

        # Run 1: both jobs A and B are active
        evals1, _, _ = JobDiscoveryPipeline(
            sources=[_DynamicSource([job_a, job_b])], state_store=self.store
        ).run(query="")
        self.assertEqual(len(evals1), 2)
        ids = {e.normalized_job.company: e.job_id for e in evals1}
        self.assertTrue(self.store.get(ids["Alpha"]).is_active)
        self.assertTrue(self.store.get(ids["Beta"]).is_active)

        # Run 2: job B disappears from scrape, and job C returns "Skelbimas neaktyvus"
        job_c_expired = RawJobListing(
            raw_id="c1", title="AI Developer", company="Gamma",
            location_raw="Vilnius", description_raw="Skelbimas neaktyvus. Darbo pasiūlymas nebegalioja.",
            job_url="https://example.com/c1", source="dyn",
        )
        evals2, _, _ = JobDiscoveryPipeline(
            sources=[_DynamicSource([job_a, job_c_expired])], state_store=self.store
        ).run(query="")
        self.assertEqual(len(evals2), 1)
        self.assertEqual(evals2[0].job_id, ids["Alpha"])
        self.assertTrue(self.store.get(ids["Alpha"]).is_active)
        self.assertFalse(self.store.get(ids["Beta"]).is_active)

    def test_prompt_version_bump_triggers_reevaluation(self):
        from execution import agentic_extractor as extractor_mod

        job = RawJobListing(
            raw_id="v1", title="Junior AI Intern", company="Alpha",
            location_raw="Vilnius", description_raw="Python AI role for students.",
            job_url="https://example.com/v1", source="test",
        )

        class _SingleSource(JobSource):
            @property
            def source_name(self) -> str:
                return "single"

            def fetch_jobs(self, query: str = "", limit: int = 20):
                return [job]

        store = JobStateStore(":memory:", evaluator_version_suffix="+llm:fake:p1")
        with patch.object(extractor_mod, "PROMPT_VERSION", "1"):
            p1 = JobDiscoveryPipeline(sources=[_SingleSource()], state_store=store)
            p1.run(query="")
            self.assertEqual(p1.last_run_stats["evaluated"], 1)

        # Now PROMPT_VERSION is "2" -> stored "+llm:fake:p1" is detected as stale and re-evaluated
        store.evaluator_version_suffix = "+llm:fake:p2"
        p2 = JobDiscoveryPipeline(sources=[_SingleSource()], state_store=store)
        p2.run(query="")
        self.assertEqual(p2.last_run_stats["evaluated"], 1)
        self.assertEqual(p2.last_run_stats["cached"], 0)
        store.close()


if __name__ == "__main__":
    unittest.main()
