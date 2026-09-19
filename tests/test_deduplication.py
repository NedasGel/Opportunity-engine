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


if __name__ == "__main__":
    unittest.main()
