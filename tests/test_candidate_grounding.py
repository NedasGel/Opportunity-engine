import unittest
from execution.models import (
    CandidateProfile, RawJobListing, Recommendation
)
from execution.normalize import normalize_job
from execution.evaluate import evaluate_job


class TestCandidateGrounding(unittest.TestCase):

    def setUp(self):
        self.profile = CandidateProfile()

    def test_candidate_profile_facts(self):
        self.assertEqual(self.profile.professional_technical_experience_years, 0)
        self.assertFalse(self.profile.completed_degree)
        self.assertIn("Lithuanian", self.profile.spoken_languages)
        self.assertIn("English", self.profile.spoken_languages)
        self.assertIn("Barbora courier", self.profile.non_technical_experience)
        self.assertIn("Bolt courier", self.profile.non_technical_experience)

    def test_application_draft_never_fabricates_experience(self):
        raw = RawJobListing(
            raw_id="apply-test",
            title="Junior AI Automation Specialist",
            company="AutomaCorp",
            location_raw="Vilnius",
            description_raw="Junior AI Automation role. Students welcome. Python and basic AI.",
            job_url="https://automacorp.example.com/jobs/1",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        self.assertIsNotNone(result.application_message_draft)
        draft = result.application_message_draft

        # Grounding checks: must state 2nd year AI student in Vilnius
        self.assertIn("second-year undergraduate student in Artificial Intelligence", draft)
        self.assertIn("Vilnius", draft)
        self.assertIn("Lithuanian and English", draft)

        # Forbidden claims
        self.assertNotIn("years of experience", draft.lower())
        self.assertNotIn("senior", draft.lower())
        self.assertNotIn("certified", draft.lower())
        self.assertNotIn("bachelor's degree in hand", draft.lower())


if __name__ == "__main__":
    unittest.main()
