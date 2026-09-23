import json
from typing import List, Dict, Any
from .models import EvaluationResult, Recommendation


def format_markdown_report(evaluations: List[EvaluationResult]) -> str:
    """Formats evaluated job opportunities into a clean, human-readable Markdown report."""
    lines = []
    lines.append("# Personal Job Opportunity Discovery Report")
    lines.append("")
    lines.append(f"**Total Opportunities Evaluated**: {len(evaluations)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for idx, ev in enumerate(evaluations, 1):
        job = ev.normalized_job
        sb = ev.score_breakdown
        lines.append(f"## {idx}. {job.title} — {job.company}")
        lines.append("")
        lines.append(f"- **Company**: {job.company}")
        lines.append(f"- **Location**: {job.location}")
        lines.append(f"- **Work Mode**: {job.work_mode.value.capitalize()}")
        lines.append(f"- **Employment Type**: {job.employment_type.value.replace('_', ' ').capitalize()}")
        lines.append(f"- **Salary**: {job.salary or 'Not stated'}")
        lines.append(f"- **Match Score**: **{ev.total_score}/100**")
        lines.append(f"- **Score Breakdown**: Domain: {sb.ai_relevance}/40 | Tech Skills: {sb.technical_skill_overlap}/15 | Student/Exp: {sb.student_compatibility}/20 | Schedule: {sb.schedule_compatibility}/10 | Location: {sb.location_compatibility}/10 | Language: {sb.language_compatibility}/5")
        lines.append("")

        lines.append("### WHY IT MATCHES")
        if ev.strong_matches or ev.weak_matches:
            for m in ev.strong_matches:
                lines.append(f"- [Strong Match] {m}")
            for m in ev.weak_matches:
                lines.append(f"- [Reasonable Match] {m}")
        else:
            lines.append("- No strong matching factors identified.")
        lines.append("")

        if ev.concerns:
            lines.append("### CONCERNS")
            for c in ev.concerns:
                lines.append(f"- {c}")
            lines.append("")

        if ev.missing_information:
            lines.append("### MISSING INFORMATION")
            for mi in ev.missing_information:
                lines.append(f"- {mi}")
            lines.append("")

        lines.append("### EVIDENCE")
        for item in ev.evidence_items:
            lines.append(f"- {item.format()}")
        lines.append("")

        lines.append(f"- **JOB LISTING**: {job.job_url}")
        app_url_display = job.application_url if job.application_url else "Not identified (Review listing to apply)"
        lines.append(f"- **APPLICATION**: {app_url_display}")
        lines.append(f"- **RECOMMENDATION**: **{ev.recommendation.value}**")
        lines.append("")

        if ev.application_message_draft:
            lines.append("### APPLICATION MESSAGE DRAFT (For Human Review)")
            lines.append("```text")
            lines.append(ev.application_message_draft)
            lines.append("```")
            lines.append("")

        if job.duplicate_sources:
            lines.append("### DUPLICATE SOURCES FOUND")
            for dup in job.duplicate_sources:
                lines.append(f"- Source: {dup['source']} | URL: {dup['job_url']}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def format_json_report(evaluations: List[EvaluationResult]) -> str:
    """Formats evaluated job opportunities into a structured JSON string."""
    data = []
    for ev in evaluations:
        job = ev.normalized_job
        sb = ev.score_breakdown
        data.append({
            "job_id": ev.job_id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "work_mode": job.work_mode.value,
            "employment_type": job.employment_type.value,
            "salary": job.salary,
            "total_score": ev.total_score,
            "recommendation": ev.recommendation.value,
            "score_breakdown": {
                "ai_relevance": sb.ai_relevance,
                "student_compatibility": sb.student_compatibility,
                "location_compatibility": sb.location_compatibility,
                "schedule_compatibility": sb.schedule_compatibility,
                "education_compatibility": sb.education_compatibility,
                "technical_skill_overlap": sb.technical_skill_overlap,
                "language_compatibility": sb.language_compatibility
            },
            "strong_matches": ev.strong_matches,
            "weak_matches": ev.weak_matches,
            "missing_information": ev.missing_information,
            "concerns": ev.concerns,
            "hard_blockers": ev.hard_blockers,
            "soft_penalties": ev.soft_penalties,
            "job_url": job.job_url,
            "application_url": job.application_url,
            "duplicate_sources": job.duplicate_sources,
            "evidence": [item.format() for item in ev.evidence_items],
            "application_message_draft": ev.application_message_draft
        })
    return json.dumps(data, indent=2, ensure_ascii=False)
