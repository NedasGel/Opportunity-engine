import unittest
from execution.normalize import normalize_job
from execution.evaluate import evaluate_job, CandidateProfile
from execution.models import RawJobListing, EmploymentType

class TestRegressionFixes(unittest.TestCase):
    def setUp(self):
        self.profile = CandidateProfile()

    def test_extract_salary_from_description(self):
        raw = RawJobListing(
            raw_id="test-1",
            title="AI Engineer",
            company="Test",
            location_raw="Vilnius",
            description_raw="We offer €1,710 to €4,700 gross per month for this role.",
            job_url="http://test",
            source="linkedin",
            discovery_timestamp="2026-10-07",
            salary_raw=None  # Hardcoded None like LinkedIn
        )
        job = normalize_job(raw)
        self.assertEqual(job.salary, "€1,710 to €4,700 gross per month")

    def test_extract_salary_eur_dash(self):
        raw = RawJobListing(
            raw_id="test-2",
            title="AI Engineer",
            company="Test",
            location_raw="Vilnius",
            description_raw="Salary: EUR 2000 - 3000",
            job_url="http://test",
            source="linkedin",
            discovery_timestamp="2026-10-07",
            salary_raw=None
        )
        job = normalize_job(raw)
        self.assertEqual(job.salary, "EUR 2000 - 3000")

    def test_broad_degree_patterns_bullet_point(self):
        raw = RawJobListing(
            raw_id="test-3",
            title="Software Engineer",
            company="Test",
            location_raw="Vilnius",
            description_raw="Requirements:\n- Bachelor's degree in Computer Science\n- 1 year experience",
            job_url="http://test",
            source="test",
            discovery_timestamp="2026-10-07",
            salary_raw=None
        )
        job = normalize_job(raw)
        self.assertTrue(job.degree_is_mandatory)
        self.assertTrue(job.requires_completed_degree)

    def test_junior_40_hours_schedule_conflict(self):
        raw = RawJobListing(
            raw_id="test-4",
            title="Junior AI Native Engineer",
            company="Test",
            location_raw="Vilnius",
            description_raw="This is a great role. Full-Time | 40 Hours per Week. As an AI Native Software Engineer...",
            job_url="http://test",
            source="test",
            discovery_timestamp="2026-10-07",
            salary_raw=None
        )
        job = normalize_job(raw)
        # Verify normalization correctly picked up ENTRY_LEVEL due to title
        self.assertEqual(job.employment_type, EmploymentType.ENTRY_LEVEL)

        # Verify evaluation applied the 3.0 point penalty for schedule
        result = evaluate_job(job, self.profile)
        self.assertEqual(result.score_breakdown.schedule_compatibility, 3.0)
        
        # Check that it raised a concern about full-time schedule
        self.assertTrue(any("Full-time schedule may conflict" in c for c in result.concerns))

    def test_junior_full_time_text_check(self):
        # Even if employment type isn't FULL_TIME, text text_lower should catch '40 hours'
        raw = RawJobListing(
            raw_id="test-5",
            title="Junior Engineer",
            company="Test",
            location_raw="Vilnius",
            description_raw="We expect 40 hours of commitment weekly.",
            job_url="http://test",
            source="test",
            discovery_timestamp="2026-10-07",
            salary_raw=None
        )
        job = normalize_job(raw)
        result = evaluate_job(job, self.profile)
        self.assertEqual(result.score_breakdown.schedule_compatibility, 3.0)
        self.assertTrue(any("Full-time / 40-hour schedule" in p for p in result.soft_penalties))

if __name__ == '__main__':
    unittest.main()
