import unittest
from execution.prefilter import prefilter_title, prefilter_job, fold, PREFILTER_VERSION
from execution.models import RawJobListing
from execution.normalize import normalize_job


MUST_BLOCK = [
    # Titles taken from real runs + common manual/retail/care roles (LT + EN)
    "Kelio darbininkas",
    "Pardavėjas",
    "Pardavejas",                      # no diacritics
    "Pardavėjas - konsultantas (-ė)",
    "Savarankiškas ekspeditorius",
    "Vyr. Sandėlininkas (-ė)",
    "Sandelininkas",                   # no diacritics
    "Vairuotojas kurjeris B kat.",
    "Kasininkas (-ė)",
    "Virėjas (-a)",
    "Padavėjas (-a)",
    "Valytojas (-a)",
    "Užsakymų komplektuotojas (-a)",
    "Prekių išdėstytojas (-a) naktinėje pamainoje",
    "Mėsininkas (-ė)",
    "Suvirintojas",
    "Santechnikas",
    "Mūrininkas",
    "Elektrikas",
    "Automobilių mechanikas",
    "Slaugytojas (-a)",
    "Psichologas (-ė)",
    "Socialinis (-ė) darbuotojas (-a) darbui su šeimomis",
    "Vyriausiasis restorano administratorius (-ė)",
    "Vandens filtrų montuotojas (-a)",
    "Gamybos operatorius (-ė)",
    "Warehouse Worker",
    "Delivery Driver",
    "Cashier",
    "Barista",
    "Forklift operator",
    "Sales Assistant",
]

MUST_PASS = [
    # Near-miss tech titles that share stems/words with blocked roles
    "AI Engineer (F/M/D)",
    "ML / AI inžinierius (-ės) dokumentų transkribavimo sprendimui",
    "Duomenų analitikas (-ė) (Phyton) – Junior",
    "Junior Python programuotojas",
    "Sistemų administratorius (-ė)",
    "IT tinklo administratorius (-ė)",
    "Duomenų bazių administratorius (-ė) (PostgreSQL)",
    "IT projektų vadybininkas (-ė)",
    "IT produktų technikas - vadybininkas",
    "Elektronikos inžinierius (-ė)",
    "Electrical engineer",
    "Sandėlio automatizavimo inžinierius",
    "Robotikos operatorius",
    "Duomenų operatorius",
    "Pardavimų analitikas (-ė)",
    "Pre-Sales Engineer",
    "Sales Automation Intern",
    "IT praktika",
    "PRAKTIKA IT SKYRIUJE",
    "PRAKTIKANTĖ (-AS) ŽALŲ IR KOMPENSACIJŲ SKYRIUJE",
    "Working Student_Cloud Operations Support",
    "Automatizacijos inžinierius (-ė) / PLC Programuotojas (-a)",
    "Field Service Engineer",
    "SOC analitikas (-ė)",
    "DIRBTINIO INTELEKTO INŽINIERĖ (-IUS) IT skyriuje",
    "Test Automation Engineer (Python)",
    "Digital Innovation Intern",
    "Software QA (manual)",
    "Data Intake Specialist",
    "Mechatronikos inžinierius",
    # Non-tech but not positively identified -> default pass (evaluator decides)
    "Project manager",
    "Business Assistance Specialist",
    "Pardavimų vadybininkas (-ė)",
    "Direktorius (-ė)",
]


class TestFold(unittest.TestCase):

    def test_fold_strips_lithuanian_diacritics(self):
        self.assertEqual(fold("Pardavėjas ĄČĘĖĮŠŲŪŽ"), "pardavejas aceeisuuz")

    def test_fold_empty(self):
        self.assertEqual(fold(""), "")


class TestPrefilterRules(unittest.TestCase):

    def test_must_block_titles(self):
        for title in MUST_BLOCK:
            with self.subTest(title=title):
                d = prefilter_title(title)
                self.assertFalse(d.passed, f"Expected BLOCK but passed: {title} ({d.reason})")
                self.assertTrue(d.reason.startswith("non_tech_title"))
                self.assertIsNotNone(d.matched_pattern)

    def test_must_pass_titles(self):
        for title in MUST_PASS:
            with self.subTest(title=title):
                d = prefilter_title(title)
                self.assertTrue(d.passed, f"Expected PASS but blocked: {title} ({d.reason})")

    def test_unknown_title_defaults_to_pass(self):
        d = prefilter_title("Something Completely Unclassifiable")
        self.assertTrue(d.passed)
        self.assertEqual(d.reason, "default_pass")

    def test_allowlist_beats_blocklist(self):
        d = prefilter_title("IT pardavėjas")
        self.assertTrue(d.passed)
        self.assertEqual(d.reason, "tech_allowlist")

    def test_description_override_requires_two_signals(self):
        one = prefilter_title("Kasininkas", "Darbas su kasos sistema, Python privalumas.")
        two = prefilter_title("Kasininkas", "Kursime vidinius įrankius su Python ir SQL.")
        self.assertFalse(one.passed)
        self.assertTrue(two.passed)
        self.assertTrue(two.reason.startswith("description_override"))

    def test_prefilter_job_uses_normalized_job(self):
        raw = RawJobListing(
            raw_id="x", title="Kelio darbininkas", company="Keliai UAB",
            location_raw="Kaunas", description_raw="Kelių priežiūros darbai.",
            job_url="https://example.com/1", source="test",
        )
        self.assertFalse(prefilter_job(normalize_job(raw)).passed)

    def test_version_is_defined(self):
        self.assertTrue(PREFILTER_VERSION)


if __name__ == "__main__":
    unittest.main()
