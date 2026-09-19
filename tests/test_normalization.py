import unittest
from execution.models import RawJobListing, WorkMode, EmploymentType
from execution.normalize import (
    normalize_job, clean_url, detect_work_mode, detect_employment_type,
    extract_education_rules, extract_experience_rules
)


class TestJobNormalization(unittest.TestCase):

    def test_clean_url(self):
        url_with_utm = "https://example.com/job/123?utm_source=linkedin&utm_medium=feed&ref=tracker"
        self.assertEqual(clean_url(url_with_utm), "https://example.com/job/123")
        self.assertIsNone(clean_url("invalid_url"))
        self.assertIsNone(clean_url(None))

    def test_work_mode_detection(self):
        self.assertEqual(detect_work_mode("100% remote opportunity", "Lithuania"), WorkMode.REMOTE)
        self.assertEqual(detect_work_mode("Nuotolinis darbas", "Lietuva"), WorkMode.REMOTE)
        self.assertEqual(detect_work_mode("Hibridinis darbo modelis", "Vilnius"), WorkMode.HYBRID)
        self.assertEqual(detect_work_mode("Work in office", "Vilnius"), WorkMode.ONSITE)
        self.assertEqual(detect_work_mode("Software position", ""), WorkMode.UNKNOWN)

    def test_employment_type_detection(self):
        self.assertEqual(detect_employment_type("Looking for intern", "AI Intern"), EmploymentType.INTERNSHIP)
        self.assertEqual(detect_employment_type("Praktikantas įmonei", "Praktika"), EmploymentType.INTERNSHIP)
        self.assertEqual(detect_employment_type("Part-time flexible hours", "Python Dev"), EmploymentType.PART_TIME)
        self.assertEqual(detect_employment_type("Working student role", "AI Student"), EmploymentType.WORKING_STUDENT)
        self.assertEqual(detect_employment_type("Junior developer role", "Junior Dev"), EmploymentType.ENTRY_LEVEL)
        self.assertEqual(detect_employment_type("Full-time 40h per week", "Engineer"), EmploymentType.FULL_TIME)

    def test_employment_type_internet_not_internship(self):
        # Proves that a company or description containing 'Internet' is NOT classified as INTERNSHIP
        desc = "Experienced Product Engineer at UAB „Internet Marketing Solutions“ located in Kaunas."
        title = "Experienced Product Engineer (React / Next.js)"
        self.assertEqual(detect_employment_type(desc, title), EmploymentType.UNKNOWN)
        
        # Test international / internal words as well
        self.assertEqual(detect_employment_type("International logistics platform", "Software Engineer"), EmploymentType.UNKNOWN)
        self.assertEqual(detect_employment_type("Internal systems maintenance", "DevOps Specialist"), EmploymentType.UNKNOWN)

        # Legitimate internship phrases MUST still be recognized
        self.assertEqual(detect_employment_type("Summer internship position", "Software Developer"), EmploymentType.INTERNSHIP)
        self.assertEqual(detect_employment_type("Looking for a student internship in AI", "AI Assistant"), EmploymentType.INTERNSHIP)
        self.assertEqual(detect_employment_type("Ieškomas praktikantas Vilniuje", "Python Praktika"), EmploymentType.INTERNSHIP)

    def test_education_detection(self):
        # Mandatory completed degree
        desc_mand = "Requires completed Bachelor's degree in Computer Science."
        _, req_deg, mand = extract_education_rules(desc_mand)
        self.assertTrue(req_deg)
        self.assertTrue(mand)

        # Student friendly
        desc_stud = "Open to university students currently pursuing a degree in AI."
        _, req_deg2, mand2 = extract_education_rules(desc_stud)
        self.assertFalse(req_deg2)
        self.assertFalse(mand2)

        # Preferred degree
        desc_pref = "Bachelor degree is preferred."
        _, req_deg3, mand3 = extract_education_rules(desc_pref)
        self.assertTrue(req_deg3)
        self.assertFalse(mand3)

    def test_experience_detection(self):
        # Mandatory 3+ years
        desc_senior = "Requirements: 3+ years of professional software development experience."
        yrs, is_mand = extract_experience_rules(desc_senior)
        self.assertEqual(yrs, 3)
        self.assertTrue(is_mand)

        # Preferred 1 year
        desc_pref = "1 year of Python experience preferred."
        yrs2, is_mand2 = extract_experience_rules(desc_pref)
        self.assertEqual(yrs2, 1)
        self.assertFalse(is_mand2)

        # No experience required
        desc_no_exp = "No prior experience required, full training provided."
        yrs3, is_mand3 = extract_experience_rules(desc_no_exp)
        self.assertEqual(yrs3, 0)
        self.assertFalse(is_mand3)

    def test_missing_fields_normalization(self):
        raw = RawJobListing(
            raw_id="test-1",
            title="AI Assistant",
            company="Acme Corp",
            location_raw="",
            description_raw="Simple description without metadata.",
            job_url="https://acme.example.com/job",
            salary_raw=None,
            application_url=None,
            source="test"
        )
        norm = normalize_job(raw)
        self.assertIsNotNone(norm.job_id)
        self.assertEqual(norm.location, "Unknown")
        self.assertIsNone(norm.salary)
        self.assertIsNone(norm.application_url)
        self.assertEqual(norm.work_mode, WorkMode.UNKNOWN)


    def test_senior_title_not_classified_as_internship_or_entry_level(self):
        # Senior Java engineer with mentoring junior colleagues in text must be FULL_TIME, not ENTRY_LEVEL
        desc_nfq = "In this role you will support and mentor junior colleagues and build Java services."
        title_nfq = "Senior Software Engineer (Java)"
        self.assertEqual(detect_employment_type(desc_nfq, title_nfq), EmploymentType.FULL_TIME)

        # Experienced/Senior AI consultant with 'internships' mentioned in requirements must be FULL_TIME, not INTERNSHIP
        desc_ey = "Interest in AI evidenced by personal projects, internships, or academic research."
        title_ey = "Experienced/ Senior AI Consultant"
        self.assertEqual(detect_employment_type(desc_ey, title_ey), EmploymentType.FULL_TIME)

        # Lead Architect
        desc_arch = "Lead the team and coach junior developers."
        title_arch = "Lead Cloud Architect"
        self.assertEqual(detect_employment_type(desc_arch, title_arch), EmploymentType.FULL_TIME)


if __name__ == "__main__":
    unittest.main()
