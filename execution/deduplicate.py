from typing import List, Dict
from .models import NormalizedJob, EvidenceItem, FactType


def deduplicate_jobs(jobs: List[NormalizedJob]) -> List[NormalizedJob]:
    """
    Deduplicates normalized job listings across sources.
    Merges duplicate source metadata while preserving evidence.
    """
    deduped_map: Dict[str, NormalizedJob] = {}
    url_to_id: Dict[str, str] = {}

    for job in jobs:
        # Canonical deduplication key: company + normalized_title + location
        comp_key = job.company.lower().strip()
        title_key = job.normalized_title.strip()
        loc_key = job.location.lower().strip()
        canonical_key = f"{comp_key}|{title_key}|{loc_key}"

        # Also check if job_url matches an existing listing
        matched_id = None
        if job.job_url and job.job_url in url_to_id:
            matched_id = url_to_id[job.job_url]
        elif canonical_key in deduped_map:
            matched_id = canonical_key

        if matched_id and matched_id in deduped_map:
            existing = deduped_map[matched_id]
            # Record duplicate source info
            existing.duplicate_sources.append({
                "source": job.source,
                "job_url": job.job_url,
                "salary": job.salary or "Not stated"
            })
            # Merge application URL if existing had None but duplicate found one
            if not existing.application_url and job.application_url:
                existing.application_url = job.application_url
                existing.evidence.append(EvidenceItem(
                    fact_type=FactType.FACT,
                    statement=f"Application URL identified from duplicate source '{job.source}': {job.application_url}",
                    source_reference=job.source
                ))
            # Merge any additional technical keywords
            for kw in job.technical_keywords:
                if kw not in existing.technical_keywords:
                    existing.technical_keywords.append(kw)
            
            existing.evidence.append(EvidenceItem(
                fact_type=FactType.FACT,
                statement=f"Duplicate posting detected on '{job.source}' ({job.job_url}).",
                source_reference=job.source
            ))
        else:
            deduped_map[canonical_key] = job
            if job.job_url:
                url_to_id[job.job_url] = canonical_key

    return list(deduped_map.values())
