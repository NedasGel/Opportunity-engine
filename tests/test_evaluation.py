import unittest
from execution.models import (
    RawJobListing, CandidateProfile, Recommendation, WorkMode, EmploymentType
)
from execution.normalize import normalize_job
from execution.evaluate import evaluate_job


class TestJobEvaluation(unittest.TestCase):

    def setUp(self):
        self.profile = CandidateProfile()

    def test_high_match_student_ai_role(self):
        raw = RawJobListing(
            raw_id="good-1",
            title="Junior AI & Automation Developer",
            company="AlphaTech",
            location_raw="Vilnius (Hybrid)",
            description_raw=(
                "Join AlphaTech as a Junior AI Developer. Build AI agents, LLM automations, and Python tools. "
                "Current university students welcome! Flexible 20-40h/week part-time or full-time. "
                "Requires Python and basic AI concepts. English/Lithuanian."
            ),
            job_url="https://alphatech.example.com/jobs/1",
            application_url="https://alphatech.example.com/apply/1",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        self.assertEqual(result.recommendation, Recommendation.APPLY)
        self.assertGreaterEqual(result.total_score, 80.0)
        self.assertEqual(len(result.hard_blockers), 0)
        self.assertGreaterEqual(len(result.strong_matches), 3)

    def test_hard_blocker_mandatory_degree(self):
        raw = RawJobListing(
            raw_id="blocked-degree",
            title="AI Researcher",
            company="DeepLab",
            location_raw="Vilnius",
            description_raw=(
                "Requires completed Master's degree in Artificial Intelligence or Mathematics. "
                "Must hold a university diploma. Python and PyTorch required."
            ),
            job_url="https://deeplab.example.com/jobs/2",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        self.assertEqual(result.recommendation, Recommendation.REJECT)
        self.assertTrue(any("completed Bachelor's or Master's" in b for b in result.hard_blockers))
        self.assertLessEqual(result.total_score, 35.0)

    def test_hard_blocker_mandatory_senior_experience(self):
        raw = RawJobListing(
            raw_id="blocked-exp",
            title="Senior ML Engineer",
            company="Enterprise AI Corp",
            location_raw="Remote Lithuania",
            description_raw=(
                "Requirements: 4+ years of professional experience deploying machine learning models in production."
            ),
            job_url="https://enterprise.example.com/jobs/3",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        self.assertEqual(result.recommendation, Recommendation.REJECT)
        self.assertTrue(any("4+ years mandatory professional experience" in b for b in result.hard_blockers))

    def test_hard_blocker_unsupported_language(self):
        raw = RawJobListing(
            raw_id="blocked-lang",
            title="AI Evaluator (German)",
            company="GlobalLingua",
            location_raw="Remote",
            description_raw="German language required. Only fluent German speakers.",
            job_url="https://globallingua.example.com/jobs/4",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        self.assertEqual(result.recommendation, Recommendation.REJECT)
        self.assertTrue(any("German" in b for b in result.hard_blockers))

    def test_soft_penalty_experience_preferred(self):
        raw = RawJobListing(
            raw_id="soft-pen",
            title="Junior Automation Specialist",
            company="FlowBots",
            location_raw="Vilnius (Hybrid)",
            description_raw=(
                "Junior Automation role. Python, workflow automation. "
                "1 year of experience is preferred. Students welcome."
            ),
            job_url="https://flowbots.example.com/jobs/5",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        self.assertIn(result.recommendation, [Recommendation.APPLY, Recommendation.CONSIDER])
        self.assertEqual(len(result.hard_blockers), 0)
        self.assertTrue(any("1 year of experience preferred" in p for p in result.soft_penalties))

    def test_lithuanian_city_siauliai_not_rejected(self):
        # Šiauliai must be recognized as a Lithuanian location (soft concern/penalty, not hard reject)
        raw = RawJobListing(
            raw_id="loc-siauliai",
            title="Junior Python Engineer",
            company="Baltic Tech Šiauliai",
            location_raw="Šiauliuose",
            description_raw="Junior Python developer position onsite in Šiauliai. Students welcome, no experience required.",
            job_url="https://example.com/siauliai-job",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        # Must NOT have the hard blocker claiming outside Lithuania
        self.assertFalse(any("outside Lithuania" in b for b in result.hard_blockers))
        self.assertEqual(len(result.hard_blockers), 0)
        # Should be evaluated positively overall because it is an entry-level Python student role
        self.assertIn(result.recommendation, [Recommendation.APPLY, Recommendation.CONSIDER])

    def test_senior_title_hard_blocker(self):
        # A Senior title with no experience digits in text must be blocked as Seniority Blocker
        raw = RawJobListing(
            raw_id="senior-java",
            title="Senior Software Engineer (Java)",
            company="NFQ Technologies",
            location_raw="Vilnius",
            description_raw=(
                "We build scalable software. In this role you will support and mentor junior colleagues. "
                "Stack: Java, Oracle, Docker."
            ),
            job_url="https://example.com/senior-java",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        self.assertEqual(result.recommendation, Recommendation.REJECT)
        self.assertLessEqual(result.total_score, 35.0)
        self.assertTrue(any("Senior/Lead role" in b for b in result.hard_blockers))

    def test_experienced_senior_ai_consultant_rejected(self):
        # Even if description contains the word 'internships' (e.g. evidenced by past internships),
        # an Experienced/Senior title MUST NOT become an internship and MUST be blocked
        raw = RawJobListing(
            raw_id="ey-senior",
            title="Experienced/ Senior AI Consultant",
            company="EY",
            location_raw="Vilnius",
            description_raw=(
                "Join our IT Consulting team. Requirements: Demonstrated interest and passion for AI, "
                "as evidenced by personal projects, internships, or academic research."
            ),
            job_url="https://example.com/ey-senior",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        self.assertNotEqual(norm.employment_type, EmploymentType.INTERNSHIP)
        self.assertEqual(result.recommendation, Recommendation.REJECT)
        self.assertLessEqual(result.total_score, 35.0)
        self.assertTrue(any("Senior/Lead role" in b for b in result.hard_blockers))

    def test_non_technical_accountant_ai_guarded(self):
        # A Junior Accountant role with AI mentioned in company boilerplate must NOT receive high AI score
        raw = RawJobListing(
            raw_id="jr-accountant",
            title="Junior Accountant",
            company="EY",
            location_raw="Vilnius",
            description_raw=(
                "At EY we transform businesses through AI innovation and digital services. "
                "Looking for a Junior Accountant to manage accounting documents and financial reports."
            ),
            job_url="https://example.com/accountant",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        # AI relevance score must be 0.0 (non-technical) rather than elevated AI score
        self.assertEqual(result.score_breakdown.ai_relevance, 0.0)
        self.assertNotEqual(result.recommendation, Recommendation.APPLY)
        self.assertTrue(any("Non-technical role" in c for c in result.concerns))

    def test_lithuanian_word_boundary_ai_protection(self):
        # Proves Lithuanian words with 'ai' ending (namai, psichoterapeutai) do not trigger AI relevance
        raw = RawJobListing(
            raw_id="non-ai-lithuanian",
            title="Pagalbos namai psichoterapeutai",
            company="Social Services",
            location_raw="Vilnius",
            description_raw="Ieškomi specialistai pagalbos namams.",
            job_url="https://example.com/social",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        self.assertNotIn("AI", norm.technical_keywords)
        self.assertEqual(result.score_breakdown.ai_relevance, 0.0)

    def test_reject_mid_role_mandating_production_deployment_at_scale(self):
        # Accenture: AI/ML Computational Scientist requiring proven production experience at scale
        raw = RawJobListing(
            raw_id="accenture-comp-sci",
            title="AI/ML Computational Scientist",
            company="Accenture Baltics",
            location_raw="Vilnius, Lithuania",
            description_raw=(
                "Join Accenture as an AI/ML Computational Scientist. "
                "Requirements: Proven experience as a machine learning engineer or scientist, deploying models in production at scale. "
                "Knowledge of distributed computing systems and architecture, Python, PyTorch."
            ),
            job_url="https://accenture.example.com/jobs/ai-scientist",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        self.assertEqual(result.recommendation, Recommendation.REJECT)
        self.assertLessEqual(result.total_score, 35.0)
        self.assertTrue(any("commercial production experience" in b for b in result.hard_blockers))

    def test_fullstack_ai_role_not_recommended_as_apply(self):
        # Purai tech: Full-Stack Developer (AI) requiring shipped production apps
        raw = RawJobListing(
            raw_id="purai-fullstack-ai",
            title="Full-Stack Developer (AI)",
            company="Purai tech, MB",
            location_raw="Vilnius (Hybrid)",
            description_raw=(
                "We are looking for a Full-Stack Developer (AI) to join our team. "
                "Requirements: shipped and maintained full stack applications in production, "
                "strong in TypeScript, React/Next.js, backend Node.js/Python, database schemas Postgres, "
                "live deployment & debugging. Experience with AI tools and LLM APIs is a plus."
            ),
            job_url="https://purai.example.com/jobs/fullstack-ai",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        # Must NOT be APPLY; blocked by mandatory production shipping requirement
        self.assertEqual(result.recommendation, Recommendation.REJECT)
        self.assertLessEqual(result.total_score, 35.0)
        self.assertLess(result.score_breakdown.ai_relevance, 26.0)
        self.assertTrue(any("commercial production experience" in b for b in result.hard_blockers))

    def test_fullstack_web_ai_without_production_mandate_not_apply(self):
        # A fullstack web developer role with AI wrapper tools but no deep AI work must not pass APPLY gate
        raw = RawJobListing(
            raw_id="web-ai-tools",
            title="Full-Stack Developer (AI Tools)",
            company="WebSaaS",
            location_raw="Vilnius (Hybrid)",
            description_raw=(
                "We are looking for a Full-Stack Developer to work on our web app. "
                "Stack: React, Next.js, Node.js, PostgreSQL. You will integrate OpenAI APIs into our web dashboard. "
                "Knowledge of TypeScript and web APIs required."
            ),
            job_url="https://websaas.example.com/jobs/1",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        # Must not pass APPLY gate (ai_relevance must be below 26.0)
        self.assertNotEqual(result.recommendation, Recommendation.APPLY)
        self.assertLess(result.score_breakdown.ai_relevance, 26.0)

    def test_junior_nlp_engineer_neuro_technology_remains_apply(self):
        # Junior NLP role at Neuro Technology must remain strong APPLY
        raw = RawJobListing(
            raw_id="neuro-junior-nlp",
            title="Junior NLP Engineer",
            company="Neuro Technology",
            location_raw="Vilnius",
            description_raw=(
                "Neuro Technology is seeking a Junior NLP Engineer. "
                "Work on Natural Language Processing models, transformers, and text processing pipelines using Python and PyTorch. "
                "Open to university students and recent graduates, strong foundations in machine learning."
            ),
            job_url="https://neurotechnology.example.com/jobs/nlp-junior",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        self.assertEqual(result.recommendation, Recommendation.APPLY)
        self.assertEqual(len(result.hard_blockers), 0)
        self.assertGreaterEqual(result.total_score, 80.0)
        self.assertEqual(result.score_breakdown.ai_relevance, 40.0)

    def test_simple_deployment_mention_not_blocked(self):
        # A junior role where candidates learn deployment or mention deploying without commercial mandate must not be blocked
        raw = RawJobListing(
            raw_id="jr-ml-learning-deploy",
            title="Junior Machine Learning Developer",
            company="SmartAI",
            location_raw="Vilnius (Hybrid)",
            description_raw=(
                "Junior ML Developer. Build ML models with Python and PyTorch. "
                "You will learn how to deploy models to production. "
                "Open to university students."
            ),
            job_url="https://smartai.example.com/jobs/jr-ml",
            source="test"
        )
        norm = normalize_job(raw)
        result = evaluate_job(norm, self.profile)

        self.assertEqual(result.recommendation, Recommendation.APPLY)
        self.assertFalse(any("commercial production experience" in b for b in result.hard_blockers))


if __name__ == "__main__":
    unittest.main()

