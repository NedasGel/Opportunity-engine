from datetime import datetime, timezone
from typing import List
from .base import JobSource
from ..models import RawJobListing


class MockJobSource(JobSource):
    """Provides deterministic fixture data for testing and offline development."""

    @property
    def source_name(self) -> str:
        return "mock_fixtures"

    def fetch_jobs(self, query: str = "", limit: int = 20) -> List[RawJobListing]:
        now = datetime.now(timezone.utc).isoformat()
        fixtures = [
            RawJobListing(
                raw_id="mock-001",
                title="Junior AI & Automation Developer",
                company="NeuroTech Baltic",
                location_raw="Vilnius, Lithuania (Hybrid)",
                description_raw=(
                    "We are looking for a Junior AI & Automation Developer to join our team in Vilnius. "
                    "Responsibilities include building Python-based workflow automations, integrating LLM APIs, "
                    "and experimenting with AI agents. "
                    "Requirements: Strong interest in Artificial Intelligence, machine learning foundations, "
                    "Python programming, Git. "
                    "Current university students (2nd-4th year) are encouraged to apply! "
                    "Flexible working hours (part-time or full-time) compatible with studies. "
                    "Languages: Fluent English or Lithuanian. Salary: 1000 - 1500 EUR/month."
                ),
                job_url="https://neurotech-baltic.example.com/careers/junior-ai-developer?utm_source=linkedin",
                application_url="https://neurotech-baltic.example.com/apply/junior-ai-developer",
                salary_raw="1000 - 1500 EUR/month",
                source="mock_fixtures",
                discovery_timestamp=now
            ),
            RawJobListing(
                raw_id="mock-002",
                title="Machine Learning Intern",
                company="Nordic Data Dynamics",
                location_raw="Remote (Lithuania / EU)",
                description_raw=(
                    "Nordic Data Dynamics is hiring a paid Machine Learning Intern for our 6-month summer/fall program. "
                    "You will assist research engineers in data preprocessing, training scikit-learn and PyTorch models, "
                    "and benchmarking computer vision pipelines. "
                    "No prior professional experience required. Bachelor's or Master's studies in progress (AI/CS). "
                    "20-30 hours per week, fully remote. English required."
                ),
                job_url="https://nordicdata.example.com/internships/ml-intern",
                application_url="https://nordicdata.example.com/jobs/apply?id=ml-intern-2026",
                salary_raw="900 EUR/month",
                source="mock_fixtures",
                discovery_timestamp=now
            ),
            RawJobListing(
                raw_id="mock-003",
                title="Senior AI Platform Engineer",
                company="Global Enterprise Tech",
                location_raw="Vilnius, Lithuania",
                description_raw=(
                    "Seeking a Senior AI Engineer with 5+ years of production experience in machine learning infrastructure. "
                    "Must possess a completed Master's degree in Computer Science. "
                    "Experience leading engineering teams and managing large-scale Kubernetes clusters required."
                ),
                job_url="https://globaltech.example.com/jobs/sr-ai-eng",
                application_url="https://globaltech.example.com/apply/sr-ai-eng",
                salary_raw="5000 - 7000 EUR/month",
                source="mock_fixtures",
                discovery_timestamp=now
            ),
            RawJobListing(
                raw_id="mock-004",
                title="Junior Python / Backend Developer",
                company="VibeTech Vilnius",
                location_raw="Vilnius (On-site)",
                description_raw=(
                    "Join VibeTech as a Junior Python Developer. You will develop backend services using FastAPI, "
                    "write SQL queries, and build internal automated pipelines. "
                    "Knowledge of Python, SQL, and Git is required. 0-1 year experience preferred. "
                    "Open to talented students. Lithuanian and English languages."
                ),
                job_url="https://vibetech.example.com/careers/jr-python",
                application_url="https://vibetech.example.com/apply/jr-python",
                salary_raw="1200 - 1600 EUR/month",
                source="mock_fixtures",
                discovery_timestamp=now
            ),
            RawJobListing(
                raw_id="mock-005",
                title="AI Prompt Evaluator (German Speaker)",
                company="LinguaAI Global",
                location_raw="Remote",
                description_raw=(
                    "Evaluate and fine-tune AI model responses in German. "
                    "Mandatory native or C2 level German language required. "
                    "German only workflow."
                ),
                job_url="https://linguaai.example.com/german-evaluator",
                application_url=None,
                salary_raw="15 EUR/hour",
                source="mock_fixtures",
                discovery_timestamp=now
            ),
            RawJobListing(
                raw_id="mock-006",
                title="Junior AI & Automation Developer",
                company="NeuroTech Baltic",
                location_raw="Vilnius, Lithuania",
                description_raw=(
                    "Duplicate listing: Junior AI & Automation Developer at NeuroTech Baltic in Vilnius. "
                    "Building Python automations and LLM API integrations."
                ),
                job_url="https://cv-online.example.com/job/neurotech-ai-dev?utm_medium=feed",
                application_url="https://neurotech-baltic.example.com/apply/junior-ai-developer",
                salary_raw="1000 - 1500 EUR/month",
                source="secondary_board",
                discovery_timestamp=now
            )
        ]
        
        if query:
            q_lower = query.lower()
            return [j for j in fixtures if q_lower in j.title.lower() or q_lower in j.description_raw.lower()][:limit]
        return fixtures[:limit]
