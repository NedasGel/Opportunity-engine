"""
Tests for execution.agentic_extractor.

The LLM is replaced by a deterministic fake (`call_fn`) so these tests run
offline. They verify the plumbing: schema validation, override of the regex
values, the >1-year hard blocker, caching, fallback, and pipeline/state
integration. The *semantic* quality of the real model is checked live with:

    py -m execution.agentic_extractor
"""
import json
import unittest

from execution.agentic_extractor import (
    AgenticExtractor, RequirementExtraction, apply_extraction, parse_extraction,
    build_prompt, EXTRACTION_SCHEMA, SYSTEM_INSTRUCTION,
)
from execution.evaluate import evaluate_job, EVALUATOR_VERSION
from execution.models import CandidateProfile, RawJobListing, Recommendation
from execution.normalize import normalize_job, extract_experience_rules
from execution.pipeline import JobDiscoveryPipeline
from execution.sources.base import JobSource
from execution.state import JobStateStore


# Plain-language requirements that the regex extractor does NOT catch.
PLAIN_TEXT_2Y = "Junior-friendly team! Expect to have 2+ yrs coding in Python. We build AI agents and LLM tools."
PLAIN_TEXT_COUPLE = "You've spent a couple of years shipping production Python and machine learning services."
PREFERRED_ONLY = "Students welcome. Experience with Kubernetes for 3+ years is a plus. Python, AI agents."
STUDENT_DEGREE = "Bachelor's degree in Computer Science or currently pursuing one - students welcome. Python, ML."


def _fake_payload(required=None, preferred=None, degree=False, full_time=False, evidence=""):
    return json.dumps({
        "required_experience_years": required,
        "preferred_experience_years": preferred,
        "requires_degree": degree,
        "is_strictly_full_time": full_time,
        "evidence": evidence,
    })


# What a correct model returns for each description (stands in for Gemini).
FAKE_RESPONSES = {
    PLAIN_TEXT_2Y: _fake_payload(required=2, evidence="Expect to have 2+ yrs coding in Python"),
    PLAIN_TEXT_COUPLE: _fake_payload(required=2, full_time=True, evidence="a couple of years shipping production Python"),
    PREFERRED_ONLY: _fake_payload(required=0, preferred=3, evidence="3+ years is a plus"),
    STUDENT_DEGREE: _fake_payload(required=0, degree=False, evidence="currently pursuing one - students welcome"),
}


class FakeLLM:
    def __init__(self, responses=None, fail=False):
        self.responses = responses or FAKE_RESPONSES
        self.fail = fail
        self.calls = 0

    def __call__(self, system_instruction: str, prompt: str) -> str:
        self.calls += 1
        if self.fail:
            raise RuntimeError("HTTP 429: Too Many Requests")
        for desc, payload in self.responses.items():
            if desc in prompt:
                return payload
        return _fake_payload()


def _raw(desc, title="AI Developer", raw_id="r1"):
    return RawJobListing(
        raw_id=raw_id, title=title, company="Acme", location_raw="Vilnius (Hybrid)",
        description_raw=desc, job_url=f"https://acme.example.com/jobs/{raw_id}", source="test",
    )


def _extractor(fake=None, **kw):
    return AgenticExtractor(model="fake-model", cache_path=":memory:", call_fn=fake or FakeLLM(), max_attempts=1, **kw)


class TestRegexGap(unittest.TestCase):
    """Documents why the regex layer is being replaced."""

    def test_regex_misses_plain_text_experience(self):
        self.assertEqual(extract_experience_rules(PLAIN_TEXT_2Y), (0, False))
        self.assertEqual(extract_experience_rules(PLAIN_TEXT_COUPLE), (0, False))

    def test_regex_only_pipeline_does_not_block(self):
        result = evaluate_job(normalize_job(_raw(PLAIN_TEXT_2Y)), CandidateProfile())
        self.assertFalse(any("years mandatory" in b for b in result.hard_blockers))


class TestParseExtraction(unittest.TestCase):

    def test_valid_payload(self):
        ex = parse_extraction(_fake_payload(required=2, evidence=" quote "), model="m")
        self.assertEqual(ex.required_experience_years, 2)
        self.assertIsNone(ex.preferred_experience_years)
        self.assertEqual(ex.evidence, "quote")
        self.assertEqual(ex.model, "m")

    def test_integral_float_is_coerced(self):
        payload = json.loads(_fake_payload())
        payload["required_experience_years"] = 3.0
        self.assertEqual(parse_extraction(json.dumps(payload)).required_experience_years, 3)

    def test_rejects_invalid_output(self):
        bad = [
            "not json",
            "[]",
            json.dumps({**json.loads(_fake_payload()), "required_experience_years": True}),
            json.dumps({**json.loads(_fake_payload()), "required_experience_years": -1}),
            json.dumps({**json.loads(_fake_payload()), "required_experience_years": 99}),
            json.dumps({**json.loads(_fake_payload()), "requires_degree": "yes"}),
        ]
        for payload in bad:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    parse_extraction(payload)

    def test_schema_matches_dataclass(self):
        fields = set(RequirementExtraction.__dataclass_fields__) - {"model"}
        self.assertEqual(set(EXTRACTION_SCHEMA["properties"]), fields)
        self.assertEqual(set(EXTRACTION_SCHEMA["required"]), fields)

    def test_prompt_wraps_description_as_data(self):
        p = build_prompt("T", "D" * 20000)
        self.assertIn("JOB TITLE: T", p)
        self.assertLess(len(p), 13000)
        self.assertIn("untrusted", SYSTEM_INSTRUCTION)


class TestSemanticOverride(unittest.TestCase):

    def setUp(self):
        self.extractor = _extractor()
        self.profile = CandidateProfile()

    def tearDown(self):
        self.extractor.close()

    def _evaluate(self, desc, title="AI Developer"):
        job = normalize_job(_raw(desc, title=title))
        ex = self.extractor.extract(job.title, job.description)
        self.assertIsNotNone(ex)
        apply_extraction(job, ex)
        return job, evaluate_job(job, self.profile)

    def test_plain_text_two_years_is_hard_blocker(self):
        job, result = self._evaluate(PLAIN_TEXT_2Y)
        self.assertEqual(job.extraction_method, "llm")
        self.assertEqual(job.required_experience_years, 2)
        self.assertEqual(result.recommendation, Recommendation.REJECT)
        self.assertTrue(any("Requires 2+ years" in b for b in result.hard_blockers))
        self.assertTrue(any("Expect to have 2+ yrs" in e.statement for e in result.evidence_items))

    def test_couple_of_years_is_hard_blocker(self):
        _, result = self._evaluate(PLAIN_TEXT_COUPLE, title="ML Engineer")
        self.assertEqual(result.recommendation, Recommendation.REJECT)
        self.assertTrue(any("Requires 2+ years" in b for b in result.hard_blockers))

    def test_preferred_years_are_soft_penalty_only(self):
        job, result = self._evaluate(PREFERRED_ONLY, title="Junior AI Developer")
        self.assertFalse(job.experience_is_mandatory)
        self.assertEqual(job.min_years_experience, 3)
        self.assertFalse(any("years mandatory" in b for b in result.hard_blockers))

    def test_students_accepted_overrides_regex_degree_false_positive(self):
        regex_job = normalize_job(_raw(STUDENT_DEGREE))
        job, result = self._evaluate(STUDENT_DEGREE)
        self.assertFalse(job.degree_is_mandatory)
        self.assertFalse(any("degree" in b.lower() for b in result.hard_blockers))
        # regex evidence lines are replaced, not duplicated
        self.assertFalse(any(e.statement.startswith("Experience requirement:") for e in job.evidence))
        self.assertIsNotNone(regex_job)

    def test_one_required_year_is_not_a_blocker(self):
        ex = parse_extraction(_fake_payload(required=1))
        job = apply_extraction(normalize_job(_raw("Python AI role")), ex)
        result = evaluate_job(job, self.profile)
        self.assertFalse(any("years mandatory" in b for b in result.hard_blockers))

    def test_strict_full_time_flag_drives_schedule(self):
        ex = parse_extraction(_fake_payload(full_time=False))
        job = apply_extraction(normalize_job(_raw("Full-time or part-time, flexible for students. Python AI.")), ex)
        result = evaluate_job(job, self.profile)
        self.assertFalse(any("Full-time / 40-hour" in p for p in result.soft_penalties))


class TestExtractorRuntime(unittest.TestCase):

    def test_cache_prevents_repeat_calls(self):
        fake = FakeLLM()
        extractor = _extractor(fake)
        extractor.extract("AI Developer", PLAIN_TEXT_2Y)
        extractor.extract("AI Developer", PLAIN_TEXT_2Y)
        self.assertEqual(fake.calls, 1)
        self.assertEqual(extractor.stats, {"llm": 1, "cache": 1, "failed": 0})
        extractor.close()

    def test_failure_returns_none_and_records_error(self):
        extractor = _extractor(FakeLLM(fail=True))
        self.assertIsNone(extractor.extract("AI Developer", PLAIN_TEXT_2Y))
        self.assertEqual(extractor.stats["failed"], 1)
        self.assertIn("429", extractor.last_errors[-1])
        extractor.close()

    def test_batch_preserves_order(self):
        extractor = _extractor(max_workers=4)
        descs = [PLAIN_TEXT_2Y, PREFERRED_ONLY, STUDENT_DEGREE, PLAIN_TEXT_COUPLE]
        results = extractor.extract_many([("T", d) for d in descs])
        self.assertEqual([r.required_experience_years for r in results], [2, 0, 0, 2])
        extractor.close()


class _PlainTextSource(JobSource):
    @property
    def source_name(self) -> str:
        return "plain"

    def fetch_jobs(self, query: str = "", limit: int = 20):
        return [
            _raw(PLAIN_TEXT_2Y, title="Python AI Developer", raw_id="p1"),
            _raw(PREFERRED_ONLY, title="Junior AI Developer", raw_id="p2"),
        ]


class TestPipelineIntegration(unittest.TestCase):

    def test_pipeline_applies_extraction_and_tags_cache_version(self):
        extractor = _extractor()
        store = JobStateStore(":memory:", evaluator_version_suffix=f"+{extractor.version_tag}")
        p = JobDiscoveryPipeline(sources=[_PlainTextSource()], state_store=store, extractor=extractor)
        evaluations, _, _ = p.run(query="")
        by_title = {e.normalized_job.title: e for e in evaluations}
        self.assertEqual(by_title["Python AI Developer"].recommendation, Recommendation.REJECT)
        self.assertNotEqual(by_title["Junior AI Developer"].recommendation, Recommendation.REJECT)
        self.assertEqual(p.last_extraction_stats["llm"], 2)

        # Second run: served from evaluation cache, no new LLM calls.
        p2 = JobDiscoveryPipeline(sources=[_PlainTextSource()], state_store=store, extractor=extractor)
        p2.run(query="")
        self.assertEqual(p2.last_run_stats["cached"], 2)
        store.close()
        extractor.close()

    def test_failed_extraction_is_retried_next_run(self):
        extractor = _extractor(FakeLLM(fail=True))
        store = JobStateStore(":memory:", evaluator_version_suffix=f"+{extractor.version_tag}")
        JobDiscoveryPipeline(sources=[_PlainTextSource()], state_store=store, extractor=extractor).run(query="")
        rows = store.conn.execute("SELECT evaluator_version FROM jobs").fetchall()
        self.assertTrue(all(r[0] == EVALUATOR_VERSION for r in rows))

        p2 = JobDiscoveryPipeline(sources=[_PlainTextSource()], state_store=store, extractor=extractor)
        p2.run(query="")
        self.assertEqual(p2.last_run_stats["cached"], 0)
        self.assertEqual(p2.last_run_stats["evaluated"], 2)
        store.close()
        extractor.close()


if __name__ == "__main__":
    unittest.main()
