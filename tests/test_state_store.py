import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from execution.models import (
    RawJobListing, CandidateProfile, ApplicationStatus, APPLICATION_STATUSES,
    evaluation_to_dict, evaluation_from_dict,
)
from execution.normalize import normalize_job
from execution.evaluate import evaluate_job
from execution import state as state_mod
from execution.state import (
    JobStateStore, compute_content_hash,
    STATUS_UNSEEN, STATUS_EVALUATED, STATUS_REJECTED_PREFILTER,
)


def make_job(title="Junior AI Engineer", company="AI Baltic", location="Vilnius",
             description="Python AI position for students.", url="https://ex.com/job/1"):
    return normalize_job(RawJobListing(
        raw_id="r1", title=title, company=company, location_raw=location,
        description_raw=description, job_url=url, source="test",
    ))


class TestSerialization(unittest.TestCase):

    def test_evaluation_round_trip_is_lossless(self):
        result = evaluate_job(make_job(), CandidateProfile())
        self.assertEqual(evaluation_from_dict(evaluation_to_dict(result)), result)

    def test_legacy_evaluation_dict_without_tracking_fields_loads_defaults(self):
        result = evaluate_job(make_job(), CandidateProfile())
        payload = evaluation_to_dict(result)
        payload.pop("application_status", None)
        payload.pop("user_notes", None)
        payload["normalized_job"].pop("application_status", None)
        payload["normalized_job"].pop("user_notes", None)

        restored = evaluation_from_dict(payload)
        self.assertEqual(restored.application_status, ApplicationStatus.NEW)
        self.assertEqual(restored.user_notes, "")
        self.assertEqual(restored.normalized_job.application_status, ApplicationStatus.NEW)
        self.assertEqual(restored.normalized_job.user_notes, "")


class TestJobStateStore(unittest.TestCase):

    def setUp(self):
        self.store = JobStateStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_schema_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "state.db")
            JobStateStore(path).close()
            s2 = JobStateStore(path)
            version = s2.conn.execute("PRAGMA user_version").fetchone()[0]
            s2.close()
            self.assertEqual(version, 1)

    def test_new_job_needs_processing(self):
        job = make_job()
        self.assertIsNone(self.store.lookup(job))
        self.assertTrue(self.store.needs_processing(job, None))

    def test_touch_seen_inserts_unseen_then_bumps(self):
        job = make_job()
        with self.store.transaction():
            self.store.touch_seen(job)
        rec = self.store.get(job.job_id)
        self.assertEqual(rec.status, STATUS_UNSEEN)
        self.assertEqual(rec.seen_count, 1)
        self.assertTrue(self.store.needs_processing(job, rec))  # interrupted run is resumed

        with self.store.transaction():
            self.store.touch_seen(job)
        self.assertEqual(self.store.get(job.job_id).seen_count, 2)

    def test_evaluated_job_is_cached(self):
        job = make_job()
        result = evaluate_job(job, CandidateProfile())
        with self.store.transaction():
            self.store.mark_evaluated(result)
        rec = self.store.lookup(job)
        self.assertEqual(rec.status, STATUS_EVALUATED)
        self.assertFalse(self.store.needs_processing(job, rec))
        self.assertEqual(self.store.load_cached_result(rec), result)

    def test_force_reprocesses(self):
        job = make_job()
        with self.store.transaction():
            self.store.mark_evaluated(evaluate_job(job, CandidateProfile()))
        self.assertTrue(self.store.needs_processing(job, self.store.lookup(job), force=True))

    def test_content_change_triggers_reprocessing(self):
        job = make_job()
        with self.store.transaction():
            self.store.mark_evaluated(evaluate_job(job, CandidateProfile()))
        changed = make_job(description="Python AI position. Now requires 5 years experience.")
        self.assertEqual(changed.job_id, job.job_id)
        self.assertNotEqual(compute_content_hash(changed), compute_content_hash(job))
        self.assertTrue(self.store.needs_processing(changed, self.store.lookup(changed)))

    def test_evaluator_version_bump_triggers_reprocessing(self):
        job = make_job()
        with self.store.transaction():
            self.store.mark_evaluated(evaluate_job(job, CandidateProfile()))
        rec = self.store.lookup(job)
        with patch.object(state_mod, "EVALUATOR_VERSION", "999"):
            self.assertTrue(self.store.needs_processing(job, rec))

    def test_prefilter_version_bump_only_affects_prefiltered_rows(self):
        pf_job = make_job(title="Kelio darbininkas", company="Keliai", url="https://ex.com/pf")
        ev_job = make_job()
        with self.store.transaction():
            self.store.mark_prefiltered(pf_job, "non_tech_title: darbinink")
            self.store.mark_evaluated(evaluate_job(ev_job, CandidateProfile()))
        pf_rec, ev_rec = self.store.lookup(pf_job), self.store.lookup(ev_job)
        self.assertEqual(pf_rec.status, STATUS_REJECTED_PREFILTER)
        self.assertFalse(self.store.needs_processing(pf_job, pf_rec))
        with patch.object(state_mod, "PREFILTER_VERSION", "999"):
            self.assertTrue(self.store.needs_processing(pf_job, pf_rec))
            self.assertFalse(self.store.needs_processing(ev_job, ev_rec))

    def test_prefiltered_reprocessed_when_prefilter_disabled(self):
        pf_job = make_job(title="Kelio darbininkas", company="Keliai", url="https://ex.com/pf")
        with self.store.transaction():
            self.store.mark_prefiltered(pf_job, "non_tech_title: darbinink")
        rec = self.store.lookup(pf_job)
        self.assertTrue(self.store.needs_processing(pf_job, rec, prefilter_enabled=False))

    def test_url_alias_lookup_resolves_changed_job_id(self):
        original = make_job(location="Lithuania", url="https://ex.com/same")
        with self.store.transaction():
            self.store.mark_evaluated(evaluate_job(original, CandidateProfile()))
        # Same posting, location resolved differently -> different job_id, same URL
        moved = make_job(location="Vilnius", url="https://ex.com/same")
        self.assertNotEqual(moved.job_id, original.job_id)
        rec = self.store.lookup(moved)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.job_id, original.job_id)

    def test_transaction_rolls_back_on_error(self):
        job = make_job()
        with self.assertRaises(RuntimeError):
            with self.store.transaction():
                self.store.touch_seen(job)
                raise RuntimeError("boom")
        self.assertIsNone(self.store.get(job.job_id))
        n = self.store.conn.execute("SELECT COUNT(*) FROM job_urls").fetchone()[0]
        self.assertEqual(n, 0)

    def test_status_constraint_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store.transaction():
                self.store.conn.execute(
                    "INSERT INTO jobs (job_id, status, title, company, content_hash, first_seen_at, last_seen_at) "
                    "VALUES ('x', 'BOGUS', 't', 'c', 'h', 'now', 'now')"
                )

    def test_run_bookkeeping(self):
        run_id = self.store.start_run()
        self.store.finish_run(run_id, {"discovered": 5, "new": 5, "prefiltered": 1, "evaluated": 4, "cached": 0})
        row = self.store.conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        self.assertEqual(row["evaluated"], 4)
        self.assertIsNotNone(row["finished_at"])

    def test_application_status_and_notes_update_and_persist(self):
        job = make_job()
        result = evaluate_job(job, CandidateProfile())
        with self.store.transaction():
            self.store.mark_evaluated(result)

        rec = self.store.get(job.job_id)
        self.assertEqual(rec.application_status, "NEW")
        self.assertEqual(rec.user_notes, "")

        for status in APPLICATION_STATUSES:
            note = f"Note for {status}"
            ok = self.store.update_application_status(job.job_id, status, user_notes=note)
            self.assertTrue(ok)
            updated_rec = self.store.get(job.job_id)
            self.assertEqual(updated_rec.application_status, status)
            self.assertEqual(updated_rec.user_notes, note)
            cached = self.store.load_cached_result(updated_rec)
            self.assertEqual(cached.application_status, status)
            self.assertEqual(cached.user_notes, note)

        self.assertTrue(self.store.update_user_notes(job.job_id, "Updated note only"))
        final_rec = self.store.get(job.job_id)
        self.assertEqual(final_rec.application_status, "ARCHIVED")
        self.assertEqual(final_rec.user_notes, "Updated note only")

    def test_invalid_application_status_rejected(self):
        job = make_job()
        with self.store.transaction():
            self.store.mark_evaluated(evaluate_job(job, CandidateProfile()))
        with self.assertRaises(ValueError):
            self.store.update_application_status(job.job_id, "INVALID_STATUS")

    def test_reevaluation_never_overwrites_application_status_or_notes(self):
        job = make_job()
        with self.store.transaction():
            self.store.mark_evaluated(evaluate_job(job, CandidateProfile()))

        self.store.update_application_status(
            job.job_id, ApplicationStatus.APPLIED, user_notes="Sent CV via LinkedIn"
        )

        # Re-evaluating the same job with a fresh EvaluationResult (default NEW / empty notes)
        fresh_result = evaluate_job(job, CandidateProfile())
        self.assertEqual(fresh_result.application_status, ApplicationStatus.NEW)
        self.assertEqual(fresh_result.user_notes, "")

        with self.store.transaction():
            self.store.mark_evaluated(fresh_result)

        rec = self.store.get(job.job_id)
        self.assertEqual(rec.application_status, "APPLIED")
        self.assertEqual(rec.user_notes, "Sent CV via LinkedIn")
        cached = self.store.load_cached_result(rec)
        self.assertEqual(cached.application_status, ApplicationStatus.APPLIED)
        self.assertEqual(cached.user_notes, "Sent CV via LinkedIn")

    def test_legacy_sqlite_schema_migrates_seamlessly(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "legacy.db")
            conn = sqlite3.connect(db_path)
            conn.executescript("""
                CREATE TABLE jobs (
                    job_id             TEXT PRIMARY KEY,
                    status             TEXT NOT NULL,
                    title              TEXT NOT NULL,
                    company            TEXT NOT NULL,
                    location           TEXT,
                    source             TEXT,
                    job_url            TEXT,
                    content_hash       TEXT NOT NULL,
                    prefilter_reason   TEXT,
                    prefilter_version  TEXT,
                    evaluator_version  TEXT,
                    recommendation     TEXT,
                    total_score        REAL,
                    evaluation_json    TEXT,
                    first_seen_at      TEXT NOT NULL,
                    last_seen_at       TEXT NOT NULL,
                    evaluated_at       TEXT,
                    seen_count         INTEGER NOT NULL DEFAULT 1
                );
                INSERT INTO jobs (job_id, status, title, company, content_hash, first_seen_at, last_seen_at)
                VALUES ('legacy-1', 'EVALUATED', 'AI Intern', 'Acme', 'hash1', '2026-01-01', '2026-01-01');
            """)
            conn.close()

            with JobStateStore(db_path) as store:
                rec = store.get("legacy-1")
                self.assertIsNotNone(rec)
                self.assertEqual(rec.application_status, "NEW")
                self.assertEqual(rec.user_notes, "")
                store.update_application_status("legacy-1", "SAVED", "Need to customize cover letter")
                rec2 = store.get("legacy-1")
                self.assertEqual(rec2.application_status, "SAVED")
                self.assertEqual(rec2.user_notes, "Need to customize cover letter")


class TestDashboardTracking(unittest.TestCase):

    def test_dashboard_load_and_persist_tracking(self):
        import dashboard

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "dash.db")
            job = make_job()
            with JobStateStore(db_path) as store:
                with store.transaction():
                    store.mark_evaluated(evaluate_job(job, CandidateProfile()))

            dashboard.load_data.clear()
            jobs = dashboard.load_data(db_path=db_path)
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["application_status"], "NEW")
            self.assertEqual(jobs[0]["user_notes"], "")
            self.assertEqual(dashboard.format_status_badge("NEW"), "🆕 NEW")
            self.assertEqual(dashboard.format_status_badge("APPLIED"), "📨 APPLIED")

            ok = dashboard.persist_job_tracking(
                job_id=job.job_id,
                application_status="SAVED",
                user_notes="Follow up Monday",
                db_path=db_path,
            )
            self.assertTrue(ok)

            jobs_after = dashboard.load_data(db_path=db_path)
            self.assertEqual(jobs_after[0]["application_status"], "SAVED")
            self.assertEqual(jobs_after[0]["user_notes"], "Follow up Monday")

    def test_dashboard_filter_hides_expired_new_jobs_but_keeps_pinned_statuses(self):
        import dashboard
        from execution.models import ACTIVE_APPLICATION_STATUSES

        sample_jobs = [
            {"job_id": "active-new", "recommendation": "APPLY", "total_score": 90.0, "application_status": "NEW", "is_active": True},
            {"job_id": "expired-new", "recommendation": "APPLY", "total_score": 85.0, "application_status": "NEW", "is_active": False},
            {"job_id": "expired-saved", "recommendation": "APPLY", "total_score": 80.0, "application_status": "SAVED", "is_active": False},
            {"job_id": "expired-applied", "recommendation": "CONSIDER", "total_score": 78.0, "application_status": "APPLIED", "is_active": False},
            {"job_id": "expired-interview", "recommendation": "CONSIDER", "total_score": 76.0, "application_status": "INTERVIEW", "is_active": False},
            {"job_id": "expired-offer", "recommendation": "APPLY", "total_score": 95.0, "application_status": "OFFER", "is_active": False},
            {"job_id": "expired-archived", "recommendation": "APPLY", "total_score": 88.0, "application_status": "ARCHIVED", "is_active": False},
        ]

        # Default view (show_historical=False): hides expired NEW, keeps active NEW + pinned statuses
        default_filtered = dashboard.filter_dashboard_jobs(
            sample_jobs,
            selected_statuses=list(ACTIVE_APPLICATION_STATUSES),
            selected_tiers=["APPLY", "CONSIDER"],
            min_score=0.0,
            show_historical=False,
        )
        default_ids = [j["job_id"] for j in default_filtered]
        self.assertIn("active-new", default_ids)
        self.assertNotIn("expired-new", default_ids)
        self.assertIn("expired-saved", default_ids)
        self.assertIn("expired-applied", default_ids)
        self.assertIn("expired-interview", default_ids)
        self.assertIn("expired-offer", default_ids)
        self.assertNotIn("expired-archived", default_ids)

        # Historical view (show_historical=True): also includes expired NEW
        hist_filtered = dashboard.filter_dashboard_jobs(
            sample_jobs,
            selected_statuses=list(ACTIVE_APPLICATION_STATUSES),
            selected_tiers=["APPLY", "CONSIDER"],
            min_score=0.0,
            show_historical=True,
        )
        hist_ids = [j["job_id"] for j in hist_filtered]
        self.assertIn("expired-new", hist_ids)


if __name__ == "__main__":
    unittest.main()
