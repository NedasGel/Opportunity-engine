"""
Tests for holistic implicit-concern detection.

The LLM is replaced by a deterministic fake payload; these tests verify the
plumbing and the scoring POLICY in evaluate.py (penalties, diminishing returns,
caps, recommendation gates), salary normalisation, evidence grounding, and
serialization round-trips.
"""
import json
import unittest

from execution.agentic_extractor import (
    AgenticExtractor, apply_extraction, parse_extraction,
    normalize_salary_to_monthly_gross_eur, is_quote_grounded,
)
from execution.evaluate import (
    evaluate_job, score_implicit_concerns, MAX_IMPLICIT_PENALTY, SCORE_COMPONENT_MAX,
    IMPLICIT_BLOCKER_PREFIX,
)
from execution.models import (
    CandidateProfile, ImplicitConcern, RawJobListing, Recommendation,
    evaluation_from_dict, evaluation_to_dict,
)
from execution.normalize import normalize_job


GOOD_JUNIOR_DESC = (
    "Join AlphaTech as a Junior AI Developer. Build AI agents, LLM automations, and Python tools. "
    "Current university students welcome! Flexible 20-40h/week part-time or full-time. "
    "Requires Python and basic AI concepts. English/Lithuanian."
)

HIDDEN_SENIOR_DESC = (
    "As our AI Solutions Developer you will own the end-to-end architecture of our GenAI platform, "
    "run discovery workshops with enterprise customers and guide the technical direction of the team. "
    "Python, LLMs, AI agents, Azure. Hybrid in Vilnius."
)


def _payload(seniority="junior", concerns=None, salary=None, **core):
    data = {
        "required_experience_years": core.get("required", 0),
        "preferred_experience_years": None,
        "requires_degree": False,
        "is_strictly_full_time": False,
        "evidence": "",
        "seniority_level": seniority,
        "implicit_concerns": concerns or [],
        "salary": salary or {"min": None, "max": None, "currency": "NONE", "period": "unknown", "basis": "unknown"},
    }
    return json.dumps(data)


def _concern(category, severity, evidence, description="Concern for a student."):
    return {"category": category, "severity": severity, "description": description, "evidence": evidence}


def _job(desc, title, salary_raw=None):
    return normalize_job(RawJobListing(
        raw_id="ic", title=title, company="Acme", location_raw="Vilnius (Hybrid)",
        description_raw=desc, job_url="https://acme.example.com/jobs/ic", source="test",
        salary_raw=salary_raw,
    ))


def _evaluate(desc, title, payload, salary_raw=None):
    job = apply_extraction(_job(desc, title, salary_raw), parse_extraction(payload, model="fake"))
    return job, evaluate_job(job, CandidateProfile())


class TestHiddenSeniority(unittest.TestCase):

    def test_hidden_senior_role_is_rejected_without_explicit_years(self):
        payload = _payload(
            seniority="senior",
            concerns=[
                _concern("implicit_seniority", "high", "own the end-to-end architecture of our GenAI platform"),
                _concern("client_facing_leadership", "high", "run discovery workshops with enterprise customers"),
            ],
            salary={"min": 5000, "max": 6500, "currency": "EUR", "period": "month", "basis": "gross"},
        )
        job, result = _evaluate(HIDDEN_SENIOR_DESC, "AI Solutions Developer", payload, "5000 - 6500 EUR bruto")

        self.assertEqual(job.required_experience_years, 0)  # nothing explicit...
        self.assertEqual(result.recommendation, Recommendation.REJECT)  # ...but still rejected
        self.assertTrue(any(b.startswith(IMPLICIT_BLOCKER_PREFIX) for b in result.hard_blockers))
        sources = {c.source for c in result.implicit_concerns}
        self.assertEqual(sources, {"llm", "seniority_assessment", "salary"})
        self.assertEqual(result.score_breakdown.implicit_concern_penalty, MAX_IMPLICIT_PENALTY)
        self.assertEqual(result.implicit_concerns[0].severity, "critical")  # sorted most severe first

    def test_single_high_concern_caps_apply_to_consider(self):
        payload = _payload(concerns=[_concern("demanding_schedule", "high", "Flexible 20-40h/week")])
        _, result = _evaluate(GOOD_JUNIOR_DESC, "Junior AI & Automation Developer", payload)
        self.assertEqual(result.recommendation, Recommendation.CONSIDER)
        self.assertTrue(any("capped at CONSIDER" in p for p in result.soft_penalties))
        self.assertEqual(result.score_breakdown.implicit_concern_penalty, 10.0)

    def test_two_high_concerns_cap_at_low_priority(self):
        payload = _payload(concerns=[
            _concern("demanding_schedule", "high", "Flexible 20-40h/week"),
            _concern("production_ownership", "high", "Build AI agents, LLM automations"),
        ])
        _, result = _evaluate(GOOD_JUNIOR_DESC, "Junior AI & Automation Developer", payload)
        self.assertEqual(result.recommendation, Recommendation.LOW_PRIORITY)

    def test_clean_junior_role_is_unaffected(self):
        _, result = _evaluate(GOOD_JUNIOR_DESC, "Junior AI & Automation Developer", _payload())
        self.assertEqual(result.recommendation, Recommendation.APPLY)
        self.assertEqual(result.score_breakdown.implicit_concern_penalty, 0.0)
        self.assertEqual(result.implicit_concerns, [])

    def test_regex_only_run_flags_missing_analysis(self):
        result = evaluate_job(_job(GOOD_JUNIOR_DESC, "Junior AI Developer"), CandidateProfile())
        self.assertTrue(any("Implicit concern analysis unavailable" in m for m in result.missing_information))


class TestScoringPolicy(unittest.TestCase):

    def test_same_category_has_diminishing_returns(self):
        total, scored = score_implicit_concerns([
            ImplicitConcern("implicit_seniority", "high", "a"),
            ImplicitConcern("implicit_seniority", "high", "b"),
            ImplicitConcern("demanding_schedule", "medium", "c"),
        ])
        self.assertEqual([c.penalty for c in scored], [10.0, 5.0, 5.0])
        self.assertEqual(total, 20.0)

    def test_total_penalty_is_capped(self):
        total, scored = score_implicit_concerns(
            [ImplicitConcern(cat, "critical", "x") for cat in ("implicit_seniority", "people_management", "other")]
        )
        self.assertEqual(total, MAX_IMPLICIT_PENALTY)
        self.assertEqual(scored[-1].penalty, 0.0)

    def test_salary_only_upper_bound_is_weaker_signal(self):
        payload = _payload(salary={"min": None, "max": 5500, "currency": "EUR", "period": "month", "basis": "gross"})
        _, result = _evaluate(GOOD_JUNIOR_DESC, "Junior AI Developer", payload, "up to 5500 EUR")
        salary_concerns = [c for c in result.implicit_concerns if c.source == "salary"]
        self.assertEqual(len(salary_concerns), 1)
        self.assertEqual(salary_concerns[0].severity, "medium")

    def test_score_component_max_sums_to_100(self):
        self.assertEqual(sum(SCORE_COMPONENT_MAX.values()), 100.0)


class TestDeterministicPostProcessing(unittest.TestCase):

    def test_salary_normalisation(self):
        cases = [
            ({"min": 2000, "max": 3000, "currency": "EUR", "period": "month", "basis": "gross"}, (2000, 3000)),
            ({"min": 60000, "max": None, "currency": "EUR", "period": "year", "basis": "gross"}, (5000, None)),
            ({"min": 2500, "max": None, "currency": "EUR", "period": "month", "basis": "net"}, (4000, None)),
            ({"min": 20, "max": 30, "currency": "EUR", "period": "hour", "basis": "gross"}, (3360, 5040)),
            ({"min": 5000, "max": None, "currency": "USD", "period": "month", "basis": "gross"}, (None, None)),
            ({"min": 5000, "max": None, "currency": "EUR", "period": "unknown", "basis": "gross"}, (None, None)),
        ]
        for salary, expected in cases:
            with self.subTest(salary=salary):
                self.assertEqual(normalize_salary_to_monthly_gross_eur(salary), expected)

    def test_quote_grounding(self):
        text = "You will OWN the   end-to-end architecture of our platform and mentor juniors."
        self.assertTrue(is_quote_grounded("own the end-to-end architecture", text))
        self.assertTrue(is_quote_grounded("own the end-to-end ... mentor juniors", text))
        self.assertFalse(is_quote_grounded("lead a team of 10 engineers", text))
        self.assertFalse(is_quote_grounded("", text))

    def test_hallucinated_quote_is_downgraded(self):
        payload = _payload(concerns=[
            _concern("people_management", "critical", "manage a team of 12 engineers"),  # not in listing
            _concern("other", "low", "invented low-severity quote"),                      # dropped
        ])
        job = apply_extraction(_job(GOOD_JUNIOR_DESC, "Junior AI Developer"), parse_extraction(payload))
        self.assertEqual(len(job.implicit_concerns), 1)
        self.assertEqual(job.implicit_concerns[0].severity, "high")
        self.assertIn("not verified", job.implicit_concerns[0].description)

    def test_malformed_concerns_are_dropped_not_fatal(self):
        data = json.loads(_payload())
        data["implicit_concerns"] = [
            "garbage",
            {"category": "made_up", "severity": "high", "description": "d", "evidence": "e"},
            {"category": "other", "severity": "apocalyptic", "description": "d", "evidence": "e"},
        ]
        data["seniority_level"] = "wizard"
        ex = parse_extraction(json.dumps(data))
        self.assertEqual([(c.category, c.severity) for c in ex.implicit_concerns], [("other", "high")])
        self.assertEqual(ex.seniority_level, "unclear")


class TestPersistence(unittest.TestCase):

    def test_evaluation_round_trip_with_concerns(self):
        payload = _payload(
            seniority="mid",
            concerns=[_concern("client_facing_leadership", "high", "run discovery workshops with enterprise customers")],
        )
        _, result = _evaluate(HIDDEN_SENIOR_DESC, "AI Solutions Developer", payload)
        self.assertTrue(result.implicit_concerns)
        self.assertEqual(evaluation_from_dict(evaluation_to_dict(result)), result)

    def test_extraction_cache_round_trip(self):
        payload = _payload(seniority="senior", concerns=[_concern("other", "medium", "x" * 10)])
        extractor = AgenticExtractor(model="fake", cache_path=":memory:", call_fn=lambda s, p: payload, max_attempts=1)
        first = extractor.extract("T", "D", "3000 EUR")
        second = extractor.extract("T", "D", "3000 EUR")
        self.assertEqual(first, second)
        self.assertEqual(extractor.stats, {"llm": 1, "cache": 1, "failed": 0})
        self.assertIsInstance(second.implicit_concerns[0], ImplicitConcern)
        # salary is part of the cache key
        extractor.extract("T", "D", "6000 EUR")
        self.assertEqual(extractor.stats["llm"], 2)
        extractor.close()


if __name__ == "__main__":
    unittest.main()
