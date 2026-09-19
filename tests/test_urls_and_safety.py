import unittest
from execution.models import RawJobListing
from execution.normalize import normalize_job, clean_url


class TestUrlsAndSafety(unittest.TestCase):

    def test_application_url_is_preserved_when_present(self):
        raw = RawJobListing(
            raw_id="url-1",
            title="AI Intern",
            company="NeuralLabs",
            location_raw="Vilnius",
            description_raw="AI Internship",
            job_url="https://neurallabs.example.com/jobs/intern",
            application_url="https://neurallabs.example.com/jobs/intern/apply",
            source="test"
        )
        norm = normalize_job(raw)
        self.assertEqual(norm.application_url, "https://neurallabs.example.com/jobs/intern/apply")

    def test_application_url_is_none_when_absent_never_fabricated(self):
        raw = RawJobListing(
            raw_id="url-2",
            title="AI Intern",
            company="NeuralLabs",
            location_raw="Vilnius",
            description_raw="AI Internship",
            job_url="https://neurallabs.example.com/jobs/intern",
            application_url=None,
            source="test"
        )
        norm = normalize_job(raw)
        self.assertIsNone(norm.application_url)

    def test_invalid_urls_rejected(self):
        self.assertIsNone(clean_url("not_a_valid_url"))
        self.assertIsNone(clean_url("ftp://example.com/jobs"))
        self.assertIsNone(clean_url(""))
        self.assertIsNone(clean_url(None))

    def test_tracking_params_cleaned(self):
        dirty = "https://jobs.example.com/view/123?utm_source=fb&utm_medium=cpc&utm_campaign=hiring&ref=feed"
        cleaned = clean_url(dirty)
        self.assertEqual(cleaned, "https://jobs.example.com/view/123")

    def test_failed_detail_page_fetch_does_not_fabricate_description(self):
        from execution.sources.cvbankas import extract_description_from_detail_html, CVBankasSource
        from unittest.mock import patch

        # 1. Test parser on empty or broken HTML does not hallucinate/fabricate
        self.assertIsNone(extract_description_from_detail_html("<html><body><p>404 Not Found</p></body></html>"))
        self.assertIsNone(extract_description_from_detail_html(""))

        # 2. Test CVBankasSource fallback behavior when detail page fails to load
        src = CVBankasSource()
        with patch('execution.sources.cvbankas.fetch_detail_page', return_value=None):
            # Simulate a search page HTML with 1 listing
            fake_search_html = (
                '<article class="list_article" id="job_ad_1001">'
                '<h3 class="list_h3">Data Analyst</h3>'
                '<a href="/job-1001">Link</a>'
                '<span class="dib mt5 mr5">TestCorp</span>'
                '<span class="list_city">Vilniuje</span>'
                '</article>'
            )
            with patch('urllib.request.urlopen') as mock_urlopen:
                mock_resp = mock_urlopen.return_value.__enter__.return_value
                mock_resp.read.return_value = fake_search_html.encode('utf-8')
                
                jobs = src.fetch_jobs(limit=1)
                self.assertEqual(len(jobs), 1)
                # Description must be factual fallback marking full description unavailable
                self.assertIn("could not be retrieved", jobs[0].description_raw)
                self.assertIn("TestCorp", jobs[0].description_raw)
                # Must NOT fabricate requirements or degrees
                self.assertNotIn("Master's degree mandatory", jobs[0].description_raw)
                self.assertNotIn("5 years experience required", jobs[0].description_raw)


if __name__ == "__main__":
    unittest.main()
