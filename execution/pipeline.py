import os
import argparse
from typing import Dict, List, Tuple, Optional, Set, Union
from .models import (
    CandidateProfile, RawJobListing, NormalizedJob, EvaluationResult, Recommendation
)
from .normalize import normalize_job
from .deduplicate import deduplicate_jobs
from .evaluate import evaluate_job
from .prefilter import prefilter_job, PrefilteredJob
from .state import JobStateStore, JobRecord, DEFAULT_DB_PATH, STATUS_EVALUATED, STATUS_REJECTED_PREFILTER
from .report import format_markdown_report, format_json_report
from .sources.base import JobSource
from .sources.mock_source import MockJobSource
from .sources.cvbankas import CVBankasSource
from .sources.cvonline import CVOnlineSource
from .sources.linkedin import LinkedInSource
from .sources.cvmarket import CVMarketSource
from .sources.work_in_lithuania import WorkInLithuaniaSource

# Configurable discovery queries tailored to 2nd-year AI student recall
DEFAULT_DISCOVERY_QUERIES = [
    "ai",
    "dirbtinis intelektas",
    "machine learning",
    "ml",
    "genai",
    "llm",
    "ai agents",
    "automation",
    "python",
    "data science",
    "duomenų",
    "nlp",
    "it praktika"
]


class JobDiscoveryPipeline:
    """
    Deterministic Multi-Source Job Discovery Pipeline orchestrating:
    DISCOVER -> NORMALIZE -> DEDUPLICATE -> STATE LOOKUP -> PRE-FILTER -> EVALUATE -> PERSIST -> RANK -> REPORT

    state_store=None runs statelessly (every job is pre-filtered/evaluated each run).
    """

    def __init__(
        self,
        sources: Optional[List[JobSource]] = None,
        profile: Optional[CandidateProfile] = None,
        state_store: Optional[JobStateStore] = None,
        enable_prefilter: bool = True,
        force_reeval: bool = False,
        report_scope: str = "all",
    ):
        self.sources = sources if sources is not None else [
            CVBankasSource(),
            CVOnlineSource(),
            LinkedInSource(),
            CVMarketSource(),
            WorkInLithuaniaSource()
        ]
        self.profile = profile if profile is not None else CandidateProfile()
        self.state = state_store
        self.enable_prefilter = enable_prefilter
        self.force_reeval = force_reeval
        if report_scope not in ("all", "new"):
            raise ValueError("report_scope must be 'all' or 'new'")
        self.report_scope = report_scope
        self.last_run_stats: Dict[str, int] = {}
        self.last_prefiltered: List[PrefilteredJob] = []

    def run(
        self,
        query: Optional[Union[str, List[str]]] = None,
        limit_per_source: int = 20,
        output_dir: Optional[str] = None
    ) -> Tuple[List[EvaluationResult], str, str]:
        # Determine query list
        if query is None:
            queries = DEFAULT_DISCOVERY_QUERIES
        elif isinstance(query, str):
            if query == "":
                queries = [""]
            else:
                queries = [q.strip() for q in query.split(",") if q.strip()]
        else:
            queries = query

        run_id = self.state.start_run() if self.state else None

        # 1. DISCOVER (Multi-source, Multi-query)
        raw_listings: List[RawJobListing] = []
        for src in self.sources:
            for q in queries:
                try:
                    listings = src.fetch_jobs(query=q, limit=limit_per_source)
                    raw_listings.extend(listings)
                except Exception as e:
                    print(f"[Pipeline] Source error on '{src.source_name}' with query '{q}': {e}")

        # 2. NORMALIZE
        normalized_listings: List[NormalizedJob] = [
            normalize_job(raw) for raw in raw_listings
        ]

        # 3. DEDUPLICATE (Cross-source & Cross-query deduplication)
        deduped_listings: List[NormalizedJob] = deduplicate_jobs(normalized_listings)

        # 4. STATE LOOKUP: resolve each job to its stored record (if any) and
        #    register it as seen. New jobs are inserted as UNSEEN so that an
        #    interrupted run is resumed next time.
        plan: List[Tuple[NormalizedJob, Optional[JobRecord], str]] = []
        if self.state:
            with self.state.transaction():
                for job in deduped_listings:
                    record = self.state.lookup(job)
                    key = record.job_id if record else job.job_id
                    self.state.touch_seen(job, key)
                    plan.append((job, record, key))
        else:
            plan = [(job, None, job.job_id) for job in deduped_listings]

        new_job_ids: Set[str] = set()
        cached_results: List[EvaluationResult] = []
        prefiltered: List[PrefilteredJob] = []
        to_evaluate: List[Tuple[NormalizedJob, str]] = []
        newly_prefiltered: List[Tuple[NormalizedJob, str, str]] = []

        for job, record, key in plan:
            if record is None:
                new_job_ids.add(job.job_id)

            if self.state and record and not self.state.needs_processing(
                job, record, force=self.force_reeval, prefilter_enabled=self.enable_prefilter
            ):
                if record.status == STATUS_EVALUATED:
                    cached_results.append(self.state.load_cached_result(record))
                    continue
                if record.status == STATUS_REJECTED_PREFILTER:
                    prefiltered.append(PrefilteredJob(job, record.prefilter_reason or "", from_cache=True))
                    continue

            # 5. PRE-FILTER (only for new / changed / version-bumped jobs)
            if self.enable_prefilter:
                decision = prefilter_job(job)
                if not decision.passed:
                    prefiltered.append(PrefilteredJob(job, decision.reason))
                    newly_prefiltered.append((job, decision.reason, key))
                    continue
            to_evaluate.append((job, key))

        # 6. EVALUATE (only what survived state + pre-filter)
        new_results: List[EvaluationResult] = []
        result_keys: List[str] = []
        for job, key in to_evaluate:
            new_results.append(evaluate_job(job, self.profile))
            result_keys.append(key)

        stats = {
            "discovered": len(deduped_listings),
            "new": len(new_job_ids),
            "evaluated": len(new_results),
            "cached": len(cached_results),
            "prefiltered": len(prefiltered),
        }

        # 7. PERSIST (single atomic transaction)
        if self.state:
            with self.state.transaction():
                for job, reason, key in newly_prefiltered:
                    self.state.mark_prefiltered(job, reason, key)
                for result, key in zip(new_results, result_keys):
                    self.state.mark_evaluated(result, key)
            self.state.finish_run(run_id, stats)

        self.last_run_stats = stats
        self.last_prefiltered = prefiltered

        # 8. RANK
        evaluations: List[EvaluationResult] = (
            new_results if self.report_scope == "new" else new_results + cached_results
        )
        rec_priority = {
            Recommendation.APPLY: 0,
            Recommendation.CONSIDER: 1,
            Recommendation.LOW_PRIORITY: 2,
            Recommendation.REJECT: 3
        }
        evaluations.sort(
            key=lambda ev: (rec_priority[ev.recommendation], -ev.total_score)
        )

        # 9. REPORT
        report_new_ids = new_job_ids if self.state else None
        md_report = format_markdown_report(
            evaluations,
            new_job_ids=report_new_ids,
            prefiltered=prefiltered,
            run_stats=stats,
        )
        json_report = format_json_report(evaluations, new_job_ids=report_new_ids)

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            md_path = os.path.join(output_dir, "job_discovery_report.md")
            json_path = os.path.join(output_dir, "job_discovery_report.json")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_report)
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(json_report)
            print(f"[Pipeline] Generated reports in {output_dir}")

        return evaluations, md_report, json_report


def main():
    parser = argparse.ArgumentParser(description="Run Multi-Source Opportunity Engine Job Discovery Pipeline")
    parser.add_argument("--query", type=str, default=None, help="Custom search query or comma-separated queries")
    parser.add_argument(
        "--source",
        type=str,
        default="all",
        choices=["all", "live", "mock", "cvbankas", "cvonline", "linkedin", "cvmarket", "work_in_lithuania"],
        help="Data source selector"
    )
    parser.add_argument("--limit", type=int, default=15, help="Max items per source per query")
    parser.add_argument(
        "--output",
        type=str,
        default=r"C:\Users\titit\.gemini\antigravity\scratch\opportunity-engine\.tmp",
        help="Output directory for reports"
    )
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH, help="SQLite state database path")
    parser.add_argument("--no-state", action="store_true", help="Run statelessly (ignore and do not update the state DB)")
    parser.add_argument("--no-prefilter", action="store_true", help="Disable the deterministic non-tech pre-filter")
    parser.add_argument("--force-reeval", action="store_true", help="Re-run pre-filter and evaluation for all jobs, ignoring cache")
    parser.add_argument(
        "--report-scope",
        type=str,
        default="all",
        choices=["all", "new"],
        help="'all' = cached + newly evaluated jobs; 'new' = only jobs evaluated this run"
    )

    args = parser.parse_args()

    sources: List[JobSource] = []
    if args.source == "mock":
        sources = [MockJobSource()]
    elif args.source == "cvbankas":
        sources = [CVBankasSource()]
    elif args.source == "cvonline":
        sources = [CVOnlineSource()]
    elif args.source == "linkedin":
        sources = [LinkedInSource()]
    elif args.source == "cvmarket":
        sources = [CVMarketSource()]
    elif args.source == "work_in_lithuania":
        sources = [WorkInLithuaniaSource()]
    elif args.source in ["all", "live"]:
        sources = [
            CVBankasSource(),
            CVOnlineSource(),
            LinkedInSource(),
            CVMarketSource(),
            WorkInLithuaniaSource()
        ]

    state_store = None if args.no_state else JobStateStore(args.db)
    try:
        pipeline = JobDiscoveryPipeline(
            sources=sources,
            state_store=state_store,
            enable_prefilter=not args.no_prefilter,
            force_reeval=args.force_reeval,
            report_scope=args.report_scope,
        )
        evaluations, md_report, _ = pipeline.run(
            query=args.query,
            limit_per_source=args.limit,
            output_dir=args.output
        )
        db_counts = state_store.status_counts() if state_store else {}
    finally:
        if state_store:
            state_store.close()

    stats = pipeline.last_run_stats
    print("\n" + "="*70)
    print("MULTI-SOURCE JOB DISCOVERY PIPELINE EXECUTION SUMMARY")
    print("="*70)
    print(
        f"Discovered (unique): {stats.get('discovered', 0)} | New: {stats.get('new', 0)} | "
        f"Evaluated: {stats.get('evaluated', 0)} | From cache: {stats.get('cached', 0)} | "
        f"Pre-filtered: {stats.get('prefiltered', 0)}"
    )
    print(f"Positions in report: {len(evaluations)}")
    apply_count = sum(1 for e in evaluations if e.recommendation == Recommendation.APPLY)
    consider_count = sum(1 for e in evaluations if e.recommendation == Recommendation.CONSIDER)
    low_count = sum(1 for e in evaluations if e.recommendation == Recommendation.LOW_PRIORITY)
    reject_count = sum(1 for e in evaluations if e.recommendation == Recommendation.REJECT)
    print(f"Recommendation breakdown: APPLY ({apply_count}), CONSIDER ({consider_count}), LOW_PRIORITY ({low_count}), REJECT ({reject_count})")
    if state_store:
        print(f"State DB ({args.db}): {db_counts}")
    print()


if __name__ == "__main__":
    main()
