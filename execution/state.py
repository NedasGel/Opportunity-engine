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
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from .models import NormalizedJob, EvaluationResult, evaluation_to_dict, evaluation_from_dict
from .evaluate import EVALUATOR_VERSION
from .prefilter import PREFILTER_VERSION

SCHEMA_VERSION = 1

STATUS_UNSEEN = "UNSEEN"
STATUS_REJECTED_PREFILTER = "REJECTED_PREFILTER"
STATUS_EVALUATED = "EVALUATED"

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
    seen_count         INTEGER NOT NULL DEFAULT 1
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
        with self.conn:
            self.conn.executescript(_SCHEMA)
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

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
        return JobRecord(
            job_id=row["job_id"],
            status=row["status"],
            content_hash=row["content_hash"],
            prefilter_reason=row["prefilter_reason"],
            prefilter_version=row["prefilter_version"],
            evaluator_version=row["evaluator_version"],
            evaluation_json=row["evaluation_json"],
            seen_count=row["seen_count"],
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
            return record.evaluator_version != self.evaluator_version or not record.evaluation_json
        return True

    def load_cached_result(self, record: JobRecord) -> EvaluationResult:
        if not record.evaluation_json:
            raise ValueError(f"No cached evaluation for job {record.job_id}")
        return evaluation_from_dict(json.loads(record.evaluation_json))

    # ----------------------------------------------------------------- writes
    def _add_urls(self, job: NormalizedJob, key: str) -> None:
        for url in _job_urls(job):
            self.conn.execute(
                "INSERT OR IGNORE INTO job_urls (url, job_id) VALUES (?, ?)", (url, key)
            )

    def touch_seen(self, job: NormalizedJob, key: Optional[str] = None) -> None:
        """Insert as UNSEEN if new; otherwise bump last_seen_at and seen_count."""
        key = key or job.job_id
        now = _now()
        self.conn.execute(
            """
            INSERT INTO jobs (job_id, status, title, company, location, source, job_url,
                              content_hash, first_seen_at, last_seen_at, seen_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(job_id) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                seen_count   = jobs.seen_count + 1
            """,
            (key, STATUS_UNSEEN, job.title, job.company, job.location, job.source,
             job.job_url, compute_content_hash(job), now, now),
        )
        self._add_urls(job, key)

    def _ensure_row(self, job: NormalizedJob, key: str) -> None:
        if not self.get(key):
            self.touch_seen(job, key)

    def mark_prefiltered(self, job: NormalizedJob, reason: str, key: Optional[str] = None) -> None:
        key = key or job.job_id
        self._ensure_row(job, key)
        self.conn.execute(
            """
            UPDATE jobs SET status = ?, title = ?, company = ?, location = ?, source = ?,
                job_url = ?, content_hash = ?, prefilter_reason = ?, prefilter_version = ?,
                evaluator_version = NULL, recommendation = NULL, total_score = NULL,
                evaluation_json = NULL, evaluated_at = NULL
            WHERE job_id = ?
            """,
            (STATUS_REJECTED_PREFILTER, job.title, job.company, job.location, job.source,
             job.job_url, compute_content_hash(job), reason, PREFILTER_VERSION, key),
        )
        self._add_urls(job, key)

    def mark_evaluated(
        self, result: EvaluationResult, key: Optional[str] = None, evaluator_version: Optional[str] = None
    ) -> None:
        """evaluator_version overrides the store default (used to tag regex-fallback results)."""
        job = result.normalized_job
        key = key or job.job_id
        version = evaluator_version or self.evaluator_version
        self._ensure_row(job, key)
        self.conn.execute(
            """
            UPDATE jobs SET status = ?, title = ?, company = ?, location = ?, source = ?,
                job_url = ?, content_hash = ?, prefilter_reason = NULL, prefilter_version = ?,
                evaluator_version = ?, recommendation = ?, total_score = ?,
                evaluation_json = ?, evaluated_at = ?
            WHERE job_id = ?
            """,
            (STATUS_EVALUATED, job.title, job.company, job.location, job.source,
             job.job_url, compute_content_hash(job), PREFILTER_VERSION, version,
             result.recommendation.value, result.total_score,
             json.dumps(evaluation_to_dict(result), ensure_ascii=False), _now(), key),
        )
        self._add_urls(job, key)

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
