import unittest
from execution.models import RawJobListing
from execution.normalize import normalize_job
from execution.deduplicate import deduplicate_jobs


class TestJobDeduplication(unittest.TestCase):

    def test_merge_duplicate_across_sources(self):
        raw_primary = RawJobListing(
            raw_id="raw-1",
            title="Junior AI Developer",
            company="Baltic AI Hub",
            location_raw="Vilnius",
            description_raw="Developing AI automations.",
            job_url="https://balticai.example.com/jobs/1",
            application_url="https://balticai.example.com/apply/1",
            source="company_career_page"
        )
        raw_duplicate = RawJobListing(
            raw_id="raw-2",
            title="Junior AI Developer",
            company="Baltic AI Hub",
            location_raw="Vilnius",
            description_raw="Developing AI automations with Python.",
            job_url="https://cvonline.example.com/job/balticai-1?utm_source=board",
            application_url=None,
            source="cvonline"
        )

        norm_1 = normalize_job(raw_primary)
        norm_2 = normalize_job(raw_duplicate)

        deduped = deduplicate_jobs([norm_1, norm_2])

        self.assertEqual(len(deduped), 1)
        merged = deduped[0]
        self.assertEqual(merged.company, "Baltic AI Hub")
        self.assertEqual(len(merged.duplicate_sources), 1)
        self.assertEqual(merged.duplicate_sources[0]["source"], "cvonline")
        self.assertEqual(merged.application_url, "https://balticai.example.com/apply/1")

    def test_distinct_jobs_not_merged(self):
        raw_1 = RawJobListing(
            raw_id="raw-1",
            title="Junior AI Developer",
            company="Baltic AI Hub",
            location_raw="Vilnius",
            description_raw="Job A",
            job_url="https://balticai.example.com/jobs/1",
            source="site"
        )
        raw_2 = RawJobListing(
            raw_id="raw-2",
            title="Senior AI Architect",
            company="Baltic AI Hub",
            location_raw="Vilnius",
            description_raw="Job B",
            job_url="https://balticai.example.com/jobs/2",
            source="site"
        )

        norm_1 = normalize_job(raw_1)
        norm_2 = normalize_job(raw_2)

        deduped = deduplicate_jobs([norm_1, norm_2])
        self.assertEqual(len(deduped), 2)

    def test_cross_source_company_variants_merged(self):
        # Ignitis grupė (CVBankas) vs Ignitis Group (LinkedIn) with title "AI ENGINEER (F/M/D)"
        raw_cvbankas = RawJobListing(
            raw_id="cvb-1",
            title="AI ENGINEER (F/M/D)",
            company="Ignitis grupė",
            location_raw="Vilnius",
            description_raw="Developing AI automations and agentic workflows.",
            job_url="https://www.cvbankas.lt/ai-engineer-vilniuje/12345",
            application_url="https://ignitis.talentlyft.com/jobs/ai-engineer-1",
            source="cvbankas"
        )
        raw_linkedin = RawJobListing(
            raw_id="li-1",
            title="AI ENGINEER (F/M/D)",
            company="Ignitis Group",
            location_raw="Vilnius, Lithuania",
            description_raw="Developing AI automations and agentic workflows.",
            job_url="https://www.linkedin.com/jobs/view/ai-engineer-98765",
            application_url=None,
            source="linkedin"
        )

        norm_1 = normalize_job(raw_cvbankas)
        norm_2 = normalize_job(raw_linkedin)

        deduped = deduplicate_jobs([norm_1, norm_2])
        self.assertEqual(len(deduped), 1)
        merged = deduped[0]
        self.assertEqual(merged.company, "Ignitis grupė")
        self.assertEqual(len(merged.duplicate_sources), 1)
        self.assertEqual(merged.duplicate_sources[0]["source"], "linkedin")
        self.assertEqual(merged.application_url, "https://ignitis.talentlyft.com/jobs/ai-engineer-1")

    def test_cross_source_ey_variants_merged(self):
        # EY (LinkedIn) vs Ernst & Young Baltic, UAB (CVOnline)
        raw_ey_li = RawJobListing(
            raw_id="ey-li-1",
            title="Junior AI Consultant",
            company="EY",
            location_raw="Vilnius, Lithuania",
            description_raw="AI consulting and analytics projects.",
            job_url="https://www.linkedin.com/jobs/view/ey-junior-ai-11111",
            application_url="https://ey.avature.net/careers/JobDetail/22222",
            source="linkedin"
        )
        raw_ey_cvo = RawJobListing(
            raw_id="ey-cvo-1",
            title="Junior AI Consultant",
            company="Ernst & Young Baltic, UAB",
            location_raw="Vilnius",
            description_raw="AI consulting and analytics projects for students.",
            job_url="https://cvonline.lt/lt/vacancy/ey-junior-ai-33333",
            application_url=None,
            source="cvonline"
        )

        norm_1 = normalize_job(raw_ey_li)
        norm_2 = normalize_job(raw_ey_cvo)

        deduped = deduplicate_jobs([norm_1, norm_2])
        self.assertEqual(len(deduped), 1)
        merged = deduped[0]
        self.assertEqual(merged.company, "EY")
        self.assertEqual(len(merged.duplicate_sources), 1)
        self.assertEqual(merged.duplicate_sources[0]["source"], "cvonline")
        self.assertEqual(merged.application_url, "https://ey.avature.net/careers/JobDetail/22222")

    def test_non_identical_roles_remain_distinct_with_company_variants(self):
        # Same company variations, but different seniority / roles must NOT merge
        raw_1 = RawJobListing(
            raw_id="ign-1",
            title="Junior AI Engineer",
            company="Ignitis grupė",
            location_raw="Vilnius",
            description_raw="Entry role.",
            job_url="https://www.cvbankas.lt/junior-ai/1",
            source="cvbankas"
        )
        raw_2 = RawJobListing(
            raw_id="ign-2",
            title="Senior AI Architect",
            company="Ignitis Group",
            location_raw="Vilnius, Lithuania",
            description_raw="Senior role.",
            job_url="https://www.linkedin.com/jobs/view/senior-ai/2",
            source="linkedin"
        )

        norm_1 = normalize_job(raw_1)
        norm_2 = normalize_job(raw_2)

        deduped = deduplicate_jobs([norm_1, norm_2])
        self.assertEqual(len(deduped), 2)


if __name__ == "__main__":
    unittest.main()

