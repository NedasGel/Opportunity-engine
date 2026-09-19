import unittest
from unittest.mock import patch, MagicMock
from execution.sources.cvonline import CVOnlineSource
from execution.sources.linkedin import LinkedInSource, extract_linkedin_description_html
from execution.sources.cvmarket import CVMarketSource, extract_cvmarket_detail_description
from execution.sources.work_in_lithuania import WorkInLithuaniaSource
from execution.pipeline import JobDiscoveryPipeline
from execution.models import Recommendation, WorkMode


class TestMultiSources(unittest.TestCase):

    def test_cvonline_source_offline_parsing(self):
        # Mock HTML containing __NEXT_DATA__
        mock_html = '''
        <html>
        <script id="__NEXT_DATA__" type="application/json">
        {
            "props": {
                "pageProps": {
                    "searchResults": {
                        "vacancies": [
                            {
                                "id": 999123,
                                "positionTitle": "Junior AI Developer",
                                "employerName": "Baltic AI Labs",
                                "salaryFrom": 1500,
                                "salaryTo": 2200,
                                "positionContent": "Developing Python AI agents and LLM tools. Open to university students.",
                                "remoteWork": true,
                                "remoteWorkType": "HYBRID"
                            }
                        ]
                    }
                }
            }
        }
        </script>
        </html>
        '''
        src = CVOnlineSource()
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_resp = mock_urlopen.return_value.__enter__.return_value
            mock_resp.read.return_value = mock_html.encode('utf-8')

            jobs = src.fetch_jobs(query="python", limit=5)
            self.assertEqual(len(jobs), 1)
            job = jobs[0]
            self.assertEqual(job.title, "Junior AI Developer")
            self.assertEqual(job.company, "Baltic AI Labs")
            self.assertEqual(job.salary_raw, "1500-2200 EUR/month")
            self.assertEqual(job.job_url, "https://cvonline.lt/lt/vacancy/999123")
            self.assertIn("Python AI agents", job.description_raw)
            self.assertEqual(job.source, "cvonline")

    def test_linkedin_source_offline_parsing(self):
        mock_search_html = '''
        <ul>
        <li>
            <h3 class="base-search-card__title">Junior Machine Learning Engineer</h3>
            <h4 class="base-search-card__subtitle"><a href="#">NeuroTech</a></h4>
            <span class="job-search-card__location">Vilnius, Lithuania</span>
            <a class="base-card__full-link" href="https://lt.linkedin.com/jobs/view/junior-ml-engineer-44001122?ref=123"></a>
        </li>
        </ul>
        '''
        src = LinkedInSource()
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_resp = mock_urlopen.return_value.__enter__.return_value
            mock_resp.read.return_value = mock_search_html.encode('utf-8')

            with patch('execution.sources.linkedin.fetch_linkedin_detail_description', return_value="Machine Learning and Python role."):
                jobs = src.fetch_jobs(query="machine learning", limit=5)
                self.assertEqual(len(jobs), 1)
                job = jobs[0]
                self.assertEqual(job.title, "Junior Machine Learning Engineer")
                self.assertEqual(job.company, "NeuroTech")
                self.assertEqual(job.job_url, "https://lt.linkedin.com/jobs/view/junior-ml-engineer-44001122")
                self.assertEqual(job.source, "linkedin")
                self.assertEqual(job.description_raw, "Machine Learning and Python role.")

    def test_cvmarket_source_offline_parsing(self):
        mock_cvm_html = '''
        <html>
        <a href="/junior-python-developer-vilnius-techcorp-2299001">
            <div class="f_job_title">Junior Python Developer</div>
            <span class="salary">1200 - 1800 €/mėn.</span>
        </a>
        </html>
        '''
        src = CVMarketSource()
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_resp = mock_urlopen.return_value.__enter__.return_value
            mock_resp.read.return_value = mock_cvm_html.encode('utf-8')

            with patch('execution.sources.cvmarket.fetch_cvmarket_detail', return_value="Full details about Python junior position."):
                jobs = src.fetch_jobs(query="python", limit=5)
                self.assertEqual(len(jobs), 1)
                job = jobs[0]
                self.assertEqual(job.job_url, "https://www.cvmarket.lt/junior-python-developer-vilnius-techcorp-2299001")
                self.assertEqual(job.source, "cvmarket")
                self.assertIn("1200 - 1800", job.salary_raw)

    def test_work_in_lithuania_source_graceful_handling(self):
        src = WorkInLithuaniaSource()
        # Should return empty list gracefully without throwing
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_resp = mock_urlopen.return_value.__enter__.return_value
            mock_resp.read.return_value = b"<html><div id='root'></div></html>"
            jobs = src.fetch_jobs(query="python")
            self.assertEqual(jobs, [])

    def test_pipeline_multi_source_deduplication(self):
        # Create two sources returning the same job
        mock_src1 = MagicMock()
        mock_src1.source_name = "src1"
        from execution.models import RawJobListing
        j1 = RawJobListing(
            raw_id="s1-1",
            title="Junior AI Engineer",
            company="AI Baltic",
            location_raw="Vilnius",
            description_raw="Python AI position for students.",
            job_url="https://src1.example.com/job/1",
            source="src1"
        )
        mock_src1.fetch_jobs.return_value = [j1]

        mock_src2 = MagicMock()
        mock_src2.source_name = "src2"
        j2 = RawJobListing(
            raw_id="s2-1",
            title="Junior AI Engineer",
            company="AI Baltic",
            location_raw="Vilnius",
            description_raw="Python AI position for students.",
            job_url="https://src2.example.com/job/1",
            source="src2"
        )
        mock_src2.fetch_jobs.return_value = [j2]

        pipeline = JobDiscoveryPipeline(sources=[mock_src1, mock_src2])
        evaluations, _, _ = pipeline.run(query=["ai"])

        # Two identical positions should be deduplicated to 1
        self.assertEqual(len(evaluations), 1)
        self.assertEqual(len(evaluations[0].normalized_job.duplicate_sources), 1)
        self.assertEqual(evaluations[0].normalized_job.duplicate_sources[0]["source"], "src2")


if __name__ == "__main__":
    unittest.main()
