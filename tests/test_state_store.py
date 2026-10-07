import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from execution.models import RawJobListing, CandidateProfile, evaluation_to_dict, evaluation_from_dict
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


if __name__ == "__main__":
    unittest.main()
