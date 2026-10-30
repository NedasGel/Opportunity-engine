"""
Lightweight SQLite state management for the job discovery pipeline.

Tracks every discovered job across runs so that:
  * previously evaluated jobs are served from cache instead of re-evaluated,
  * previously pre-filtered jobs are skipped,
  * jobs are re-processed automatically when their content changes or when
    the evaluator / pre-filter rule versions are bumped.

Pure stdlib (sqlite3 + json), no ORM.
"""
import hashlib
import json
import os
import sqlite3
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set, Union

from .models import (
    NormalizedJob, EvaluationResult, ApplicationStatus, APPLICATION_STATUSES,
    evaluation_to_dict, evaluation_from_dict,
)
from .evaluate import EVALUATOR_VERSION
from .prefilter import PREFILTER_VERSION

SCHEMA_VERSION = 1

STATUS_UNSEEN = "UNSEEN"
STATUS_REJECTED_PREFILTER = "REJECTED_PREFILTER"
STATUS_EVALUATED = "EVALUATED"

EXPIRED_PAGE_MARKERS = (
    "skelbimas neaktyvus",
    "skelbimas nebegalioja",
    "skelbimo galiojimo laikas baigėsi",
    "skelbimo galiojimo laikas pasibaigė",
    "skelbimas pasibaigęs",
    "skelbimas pašalintas",
    "pasiūlymas nebegalioja",
    "darbo skelbimas neaktyvus",
    "this job ad is no longer active",
    "this job is no longer available",
    "no longer accepting applications",
    "job ad has expired",
    "listing has expired",
)


def has_expired_marker(text: Optional[str]) -> bool:
    """Return True if text contains a known job-board expired-listing marker."""
    if not text:
        return False
    lowered = unescape(text).lower()
    return any(marker in lowered for marker in EXPIRED_PAGE_MARKERS)


def is_job_expired(job: NormalizedJob) -> bool:
    """Return True if a NormalizedJob's title or description indicates an expired listing."""
    return has_expired_marker(job.title) or has_expired_marker(job.description)


def check_url_is_expired(url: str, timeout: int = 8) -> bool:
    """Fetch a job URL and check whether the page shows an expired marker (or HTTP 404/410)."""
    if not url or not url.startswith("http"):
        return False
    headers = {
        "User-Agent": "OpportunityDiscoveryEngine/1.0 (Student Research Bot; polite request; +http://localhost)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "lt,en-US;q=0.7,en;q=0.3",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            return has_expired_marker(html)
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return True
        return False
    except Exception:
        return False


DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".tmp", "state", "opportunity_engine.db"
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id             TEXT PRIMARY KEY,
    status             TEXT NOT NULL CHECK (status IN
                         ('UNSEEN','REJECTED_PREFILTER','EVALUATED')),
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
    seen_count         INTEGER NOT NULL DEFAULT 1,
    application_status TEXT NOT NULL DEFAULT 'NEW' CHECK (application_status IN
                         ('NEW','SAVED','APPLIED','INTERVIEW','OFFER','ARCHIVED')),
    user_notes         TEXT NOT NULL DEFAULT '',
    is_active          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS job_urls (
    url     TEXT PRIMARY KEY,
    job_id  TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS runs (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    discovered   INTEGER,
    new_jobs     INTEGER,
    prefiltered  INTEGER,
    evaluated    INTEGER,
    cached       INTEGER
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_content_hash(job: NormalizedJob) -> str:
    """Hash of the fields that drive evaluation; a change triggers re-processing."""
    payload = f"{job.title}|{job.company}|{job.description}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _job_urls(job: NormalizedJob) -> List[str]:
    urls = [job.job_url] if job.job_url else []
    for dup in job.duplicate_sources:
        u = dup.get("job_url")
        if u and u not in urls:
            urls.append(u)
    return urls


@dataclass
class JobRecord:
    job_id: str
    status: str
    content_hash: str
    prefilter_reason: Optional[str]
    prefilter_version: Optional[str]
    evaluator_version: Optional[str]
    evaluation_json: Optional[str]
    seen_count: int
    application_status: str = ApplicationStatus.NEW.value
    user_notes: str = ""
    is_active: bool = True


def _validate_application_status(status: Union[str, ApplicationStatus]) -> str:
    val = status.value if isinstance(status, ApplicationStatus) else str(status).strip().upper()
    if val not in APPLICATION_STATUSES:
        raise ValueError(
            f"Invalid application_status '{status}'. Must be one of {APPLICATION_STATUSES}."
        )
    return val


class JobStateStore:
    """SQLite-backed job state tracker. Use ':memory:' for tests."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH, evaluator_version_suffix: str = ""):
        self.db_path = db_path
        # e.g. "+llm:gemini-3.5-flash-lite:p1" -> cache entries are tied to the extractor in use
        self.evaluator_version_suffix = evaluator_version_suffix
        if db_path != ":memory:":
            parent = os.path.dirname(os.path.abspath(db_path))
            os.makedirs(parent, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if db_path != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        self._init_schema()

    # ------------------------------------------------------------------ setup
    def _init_schema(self) -> None:
        added_is_active = False
        with self.conn:
            self.conn.executescript(_SCHEMA)
            cols = {
                row["name"] for row in self.conn.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "application_status" not in cols:
                self.conn.execute(
                    "ALTER TABLE jobs ADD COLUMN application_status TEXT NOT NULL DEFAULT 'NEW'"
                )
            if "user_notes" not in cols:
                self.conn.execute(
                    "ALTER TABLE jobs ADD COLUMN user_notes TEXT NOT NULL DEFAULT ''"
                )
            if "is_active" not in cols:
                self.conn.execute(
                    "ALTER TABLE jobs ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
                )
                added_is_active = True
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_application_status ON jobs(application_status)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_is_active ON jobs(is_active)"
            )
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        if added_is_active:
            self.reconcile_active_from_last_run()

    def reconcile_active_from_last_run(self) -> int:
        """Mark historical jobs not seen in the latest completed run (or containing expired markers) as inactive."""
        latest_run = self.conn.execute(
            "SELECT started_at FROM runs WHERE finished_at IS NOT NULL AND COALESCE(discovered, 0) > 0 "
            "ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
        marked_inactive = 0
        with self.conn:
            if latest_run and latest_run["started_at"]:
                started_at = latest_run["started_at"]
                cur = self.conn.execute(
                    "UPDATE jobs SET is_active = CASE WHEN last_seen_at >= ? THEN 1 ELSE 0 END",
                    (started_at,),
                )
                marked_inactive += cur.rowcount

            rows = self.conn.execute(
                "SELECT job_id, title, evaluation_json FROM jobs WHERE is_active = 1"
            ).fetchall()
            for r in rows:
                if has_expired_marker(r["title"]) or has_expired_marker(r["evaluation_json"]):
                    self.conn.execute(
                        "UPDATE jobs SET is_active = 0 WHERE job_id = ?", (r["job_id"],)
                    )
                    marked_inactive += 1
        return marked_inactive

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "JobStateStore":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Atomic block: commits on success, rolls back on any exception."""
        with self.conn:
            yield

    @property
    def evaluator_version(self) -> str:
        return f"{EVALUATOR_VERSION}{self.evaluator_version_suffix}"

    # ---------------------------------------------------------------- lookups
    def _row_to_record(self, row: sqlite3.Row) -> JobRecord:
        keys = row.keys()
        app_status = (
            row["application_status"]
            if "application_status" in keys and row["application_status"]
            else ApplicationStatus.NEW.value
        )
        notes = (
            row["user_notes"]
            if "user_notes" in keys and row["user_notes"] is not None
            else ""
        )
        is_active = bool(row["is_active"]) if "is_active" in keys and row["is_active"] is not None else True
        return JobRecord(
            job_id=row["job_id"],
            status=row["status"],
            content_hash=row["content_hash"],
            prefilter_reason=row["prefilter_reason"],
            prefilter_version=row["prefilter_version"],
            evaluator_version=row["evaluator_version"],
            evaluation_json=row["evaluation_json"],
            seen_count=row["seen_count"],
            application_status=app_status,
            user_notes=notes,
            is_active=is_active,
        )

    def get(self, job_id: str) -> Optional[JobRecord]:
        row = self.conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def lookup(self, job: NormalizedJob) -> Optional[JobRecord]:
        """Find a stored record by job_id, falling back to any known URL alias.

        The URL fallback covers the case where deduplication changed the job's
        location (and hence its job_id) between runs.
        """
        rec = self.get(job.job_id)
        if rec:
            return rec
        for url in _job_urls(job):
            row = self.conn.execute(
                "SELECT j.* FROM job_urls u JOIN jobs j ON j.job_id = u.job_id WHERE u.url = ?",
                (url,),
            ).fetchone()
            if row:
                return self._row_to_record(row)
        return None

    def is_version_stale(self, stored_version: Optional[str]) -> bool:
        """True if stored_version was produced by an older EVALUATOR_VERSION or PROMPT_VERSION."""
        if not stored_version:
            return True
        from . import agentic_extractor as extractor_mod

        base_ver, _, suffix = stored_version.partition("+")
        if base_ver != EVALUATOR_VERSION:
            return True
        if suffix.startswith("llm:"):
            _, p_sep, p_ver = suffix.rpartition(":p")
            if not p_sep or p_ver != str(extractor_mod.PROMPT_VERSION):
                return True
        if stored_version != self.evaluator_version:
            return True
        return False

    def needs_processing(
        self,
        job: NormalizedJob,
        record: Optional[JobRecord],
        force: bool = False,
        prefilter_enabled: bool = True,
    ) -> bool:
        if force or record is None:
            return True
        if record.status == STATUS_UNSEEN:
            return True  # interrupted previous run
        if record.content_hash != compute_content_hash(job):
            return True
        if record.status == STATUS_REJECTED_PREFILTER:
            return (not prefilter_enabled) or record.prefilter_version != PREFILTER_VERSION
        if record.status == STATUS_EVALUATED:
            return self.is_version_stale(record.evaluator_version) or not record.evaluation_json
        return True

    def load_cached_result(self, record: JobRecord) -> EvaluationResult:
        if not record.evaluation_json:
            raise ValueError(f"No cached evaluation for job {record.job_id}")
        result = evaluation_from_dict(json.loads(record.evaluation_json))
        app_status = (
            ApplicationStatus(record.application_status)
            if record.application_status in APPLICATION_STATUSES
            else ApplicationStatus.NEW
        )
        notes = record.user_notes or ""
        result.application_status = app_status
        result.user_notes = notes
        result.is_active = bool(record.is_active)
        result.normalized_job.application_status = app_status
        result.normalized_job.user_notes = notes
        result.normalized_job.is_active = bool(record.is_active)
        return result

    # ----------------------------------------------------------------- writes
    def _add_urls(self, job: NormalizedJob, key: str) -> None:
        for url in _job_urls(job):
            self.conn.execute(
                "INSERT OR IGNORE INTO job_urls (url, job_id) VALUES (?, ?)", (url, key)
            )

    def touch_seen(self, job: NormalizedJob, key: Optional[str] = None) -> None:
        """Insert as UNSEEN if new; otherwise bump last_seen_at, seen_count, and is_active."""
        key = key or job.job_id
        now = _now()
        active_val = 0 if is_job_expired(job) else 1
        self.conn.execute(
            """
            INSERT INTO jobs (job_id, status, title, company, location, source, job_url,
                              content_hash, first_seen_at, last_seen_at, seen_count, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                seen_count   = jobs.seen_count + 1,
                is_active    = excluded.is_active
            """,
            (key, STATUS_UNSEEN, job.title, job.company, job.location, job.source,
             job.job_url, compute_content_hash(job), now, now, active_val),
        )
        self._add_urls(job, key)

    def _ensure_row(self, job: NormalizedJob, key: str) -> None:
        if not self.get(key):
            self.touch_seen(job, key)

    def mark_prefiltered(self, job: NormalizedJob, reason: str, key: Optional[str] = None) -> None:
        key = key or job.job_id
        self._ensure_row(job, key)
        active_val = 0 if is_job_expired(job) else 1
        self.conn.execute(
            """
            UPDATE jobs SET status = ?, title = ?, company = ?, location = ?, source = ?,
                job_url = ?, content_hash = ?, prefilter_reason = ?, prefilter_version = ?,
                evaluator_version = NULL, recommendation = NULL, total_score = NULL,
                evaluation_json = NULL, evaluated_at = NULL, is_active = ?
            WHERE job_id = ?
            """,
            (STATUS_REJECTED_PREFILTER, job.title, job.company, job.location, job.source,
             job.job_url, compute_content_hash(job), reason, PREFILTER_VERSION, active_val, key),
        )
        self._add_urls(job, key)

    def mark_evaluated(
        self, result: EvaluationResult, key: Optional[str] = None, evaluator_version: Optional[str] = None
    ) -> None:
        """evaluator_version overrides the store default (used to tag regex-fallback results).

        CRITICAL: Never overwrites or resets an existing job's application_status or user_notes.
        """
        job = result.normalized_job
        key = key or job.job_id
        version = evaluator_version or self.evaluator_version
        existing = self.get(key)
        if not existing:
            self.touch_seen(job, key)
            existing = self.get(key)

        result_status = _validate_application_status(result.application_status or ApplicationStatus.NEW)
        result_notes = result.user_notes or job.user_notes or ""

        if existing:
            effective_status = (
                existing.application_status
                if existing.application_status != ApplicationStatus.NEW.value
                else result_status
            )
            effective_notes = existing.user_notes if existing.user_notes else result_notes
        else:
            effective_status = result_status
            effective_notes = result_notes

        active_flag = not is_job_expired(job) and bool(result.is_active)
        app_status_enum = ApplicationStatus(effective_status)
        result.application_status = app_status_enum
        result.user_notes = effective_notes
        result.is_active = active_flag
        job.application_status = app_status_enum
        job.user_notes = effective_notes
        job.is_active = active_flag

        self.conn.execute(
            """
            UPDATE jobs SET status = ?, title = ?, company = ?, location = ?, source = ?,
                job_url = ?, content_hash = ?, prefilter_reason = NULL, prefilter_version = ?,
                evaluator_version = ?, recommendation = ?, total_score = ?,
                evaluation_json = ?, evaluated_at = ?,
                application_status = ?, user_notes = ?, is_active = ?
            WHERE job_id = ?
            """,
            (STATUS_EVALUATED, job.title, job.company, job.location, job.source,
             job.job_url, compute_content_hash(job), PREFILTER_VERSION, version,
             result.recommendation.value, result.total_score,
             json.dumps(evaluation_to_dict(result), ensure_ascii=False), _now(),
             effective_status, effective_notes, 1 if active_flag else 0, key),
        )
        self._add_urls(job, key)

    def mark_inactive(self, job_id: str) -> bool:
        """Mark a job as inactive/expired (`is_active = 0`) in SQLite and cached JSON."""
        rec = self.get(job_id)
        if not rec:
            return False
        updated_eval_json = rec.evaluation_json
        if updated_eval_json:
            try:
                eval_dict = json.loads(updated_eval_json)
                if isinstance(eval_dict, dict):
                    eval_dict["is_active"] = False
                    if isinstance(eval_dict.get("normalized_job"), dict):
                        eval_dict["normalized_job"]["is_active"] = False
                    updated_eval_json = json.dumps(eval_dict, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass
        self.conn.execute(
            "UPDATE jobs SET is_active = 0, evaluation_json = ? WHERE job_id = ?",
            (updated_eval_json, job_id),
        )
        return True

    def sync_active_jobs(self, active_job_ids: Iterable[str]) -> int:
        """Mark jobs in `active_job_ids` as active (1) and all other stored jobs as inactive (0).

        Returns the number of stored jobs that are now inactive.
        """
        active_set: Set[str] = set(active_job_ids)
        rows = self.conn.execute("SELECT job_id, is_active FROM jobs").fetchall()
        inactive_count = 0
        for r in rows:
            jid = r["job_id"]
            should_be_active = jid in active_set
            if should_be_active:
                if not r["is_active"]:
                    self.conn.execute("UPDATE jobs SET is_active = 1 WHERE job_id = ?", (jid,))
            else:
                inactive_count += 1
                if r["is_active"]:
                    self.mark_inactive(jid)
        return inactive_count

    def update_job_tracking(
        self,
        job_id: str,
        application_status: Optional[Union[str, ApplicationStatus]] = None,
        user_notes: Optional[str] = None,
    ) -> bool:
        """Persist user changes to application_status and/or user_notes for a job.

        Updates both the SQL columns and any cached evaluation_json payload.
        Returns True if the job row existed and was updated, False otherwise.
        """
        rec = self.get(job_id)
        if not rec:
            return False

        new_status = (
            _validate_application_status(application_status)
            if application_status is not None
            else rec.application_status
        )
        new_notes = user_notes if user_notes is not None else rec.user_notes

        updated_eval_json = rec.evaluation_json
        if updated_eval_json:
            try:
                eval_dict = json.loads(updated_eval_json)
                if isinstance(eval_dict, dict):
                    eval_dict["application_status"] = new_status
                    eval_dict["user_notes"] = new_notes
                    if isinstance(eval_dict.get("normalized_job"), dict):
                        eval_dict["normalized_job"]["application_status"] = new_status
                        eval_dict["normalized_job"]["user_notes"] = new_notes
                    updated_eval_json = json.dumps(eval_dict, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass

        with self.conn:
            self.conn.execute(
                """
                UPDATE jobs SET application_status = ?, user_notes = ?, evaluation_json = ?
                WHERE job_id = ?
                """,
                (new_status, new_notes, updated_eval_json, job_id),
            )
        return True

    def update_application_status(
        self,
        job_id: str,
        application_status: Union[str, ApplicationStatus],
        user_notes: Optional[str] = None,
    ) -> bool:
        return self.update_job_tracking(
            job_id=job_id,
            application_status=application_status,
            user_notes=user_notes,
        )

    def update_user_notes(self, job_id: str, user_notes: str) -> bool:
        return self.update_job_tracking(job_id=job_id, user_notes=user_notes)

    # ------------------------------------------------------------------- runs
    def start_run(self) -> int:
        with self.conn:
            cur = self.conn.execute("INSERT INTO runs (started_at) VALUES (?)", (_now(),))
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, stats: Dict[str, int]) -> None:
        with self.conn:
            self.conn.execute(
                """
                UPDATE runs SET finished_at = ?, discovered = ?, new_jobs = ?,
                    prefiltered = ?, evaluated = ?, cached = ?
                WHERE run_id = ?
                """,
                (_now(), stats.get("discovered", 0), stats.get("new", 0),
                 stats.get("prefiltered", 0), stats.get("evaluated", 0),
                 stats.get("cached", 0), run_id),
            )

    # ------------------------------------------------------------- reporting
    def status_counts(self) -> Dict[str, int]:
        rows = self.conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}

    def application_status_counts(self) -> Dict[str, int]:
        rows = self.conn.execute(
            "SELECT application_status, COUNT(*) AS n FROM jobs GROUP BY application_status"
        ).fetchall()
        return {r["application_status"]: r["n"] for r in rows}
