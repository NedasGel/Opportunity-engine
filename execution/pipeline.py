import os
import argparse
from typing import List, Tuple, Optional, Union
from .models import (
    CandidateProfile, RawJobListing, NormalizedJob, EvaluationResult, Recommendation
)
from .normalize import normalize_job
from .deduplicate import deduplicate_jobs
from .evaluate import evaluate_job
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
    DISCOVER -> NORMALIZE -> DEDUPLICATE -> EVALUATE -> RANK -> REPORT
    """

    def __init__(self, sources: Optional[List[JobSource]] = None, profile: Optional[CandidateProfile] = None):
        self.sources = sources if sources is not None else [
            CVBankasSource(),
            CVOnlineSource(),
            LinkedInSource(),
            CVMarketSource(),
            WorkInLithuaniaSource()
        ]
        self.profile = profile if profile is not None else CandidateProfile()

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

        # 4. EVALUATE
        evaluations: List[EvaluationResult] = [
            evaluate_job(job, self.profile) for job in deduped_listings
        ]

        # 5. RANK
        rec_priority = {
            Recommendation.APPLY: 0,
            Recommendation.CONSIDER: 1,
            Recommendation.LOW_PRIORITY: 2,
            Recommendation.REJECT: 3
        }
        evaluations.sort(
            key=lambda ev: (rec_priority[ev.recommendation], -ev.total_score)
        )

        # 6. REPORT
        md_report = format_markdown_report(evaluations)
        json_report = format_json_report(evaluations)

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

    pipeline = JobDiscoveryPipeline(sources=sources)
    evaluations, md_report, _ = pipeline.run(
        query=args.query,
        limit_per_source=args.limit,
        output_dir=args.output
    )

    print("\n" + "="*70)
    print("MULTI-SOURCE JOB DISCOVERY PIPELINE EXECUTION SUMMARY")
    print("="*70)
    print(f"Total Evaluated Unique Positions: {len(evaluations)}")
    apply_count = sum(1 for e in evaluations if e.recommendation == Recommendation.APPLY)
    consider_count = sum(1 for e in evaluations if e.recommendation == Recommendation.CONSIDER)
    low_count = sum(1 for e in evaluations if e.recommendation == Recommendation.LOW_PRIORITY)
    reject_count = sum(1 for e in evaluations if e.recommendation == Recommendation.REJECT)
    print(f"Recommendation breakdown: APPLY ({apply_count}), CONSIDER ({consider_count}), LOW_PRIORITY ({low_count}), REJECT ({reject_count})\n")


if __name__ == "__main__":
    main()
