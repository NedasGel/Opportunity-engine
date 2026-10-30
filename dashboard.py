import streamlit as st
import sqlite3
import json
import os
from typing import Dict, List, Optional

from execution.evaluate import SCORE_COMPONENT_MAX, MAX_TOTAL_SCORE, IMPLICIT_BLOCKER_PREFIX
from execution.models import (
    ApplicationStatus, APPLICATION_STATUSES, ACTIVE_APPLICATION_STATUSES, PINNED_APPLICATION_STATUSES,
)
from execution.state import JobStateStore

DB_PATH = ".tmp/state/opportunity_engine.db"

STATUS_BADGES: Dict[str, str] = {
    ApplicationStatus.NEW.value: "🆕 NEW",
    ApplicationStatus.SAVED.value: "⭐ SAVED",
    ApplicationStatus.APPLIED.value: "📨 APPLIED",
    ApplicationStatus.INTERVIEW.value: "🗣️ INTERVIEW",
    ApplicationStatus.OFFER.value: "🎉 OFFER",
    ApplicationStatus.ARCHIVED.value: "🗄️ ARCHIVED",
}


def format_status_badge(status: Optional[str]) -> str:
    key = (status or ApplicationStatus.NEW.value).strip().upper()
    return STATUS_BADGES.get(key, f"🆕 {key}")


COMPONENT_LABELS = {
    "ai_relevance": "AI Relevance",
    "technical_skill_overlap": "Technical Skill Overlap",
    "student_compatibility": "Student Compatibility",
    "schedule_compatibility": "Schedule Compatibility",
    "location_compatibility": "Location Compatibility",
    "language_compatibility": "Language Compatibility",
}

SEVERITY_STYLE = {
    # severity: (icon, streamlit color)
    "critical": ("⛔", "red"),
    "high": ("🔴", "red"),
    "medium": ("🟠", "orange"),
    "low": ("🟡", "gray"),
}

CONCERN_SOURCE_LABELS = {
    "salary": "Derived from normalised salary",
    "seniority_assessment": "Derived from holistic seniority assessment",
}


def render_score_breakdown(breakdown: dict, total_score: float) -> None:
    if not breakdown:
        st.write("*No score breakdown available.*")
        return
    for key, max_pts in SCORE_COMPONENT_MAX.items():
        value = breakdown.get(key)
        if value is None:
            continue
        label = COMPONENT_LABELS.get(key, key.replace("_", " ").title())
        st.progress(
            min(max(value / max_pts, 0.0), 1.0) if max_pts else 0.0,
            text=f"**{label}:** {value:.1f} / {max_pts:.1f}",
        )
    penalty = breakdown.get("implicit_concern_penalty") or 0.0
    if penalty:
        st.markdown(f"**Implicit Concern Penalty:** :red[-{penalty:.1f}]")
    st.markdown(f"**Total:** {total_score:.1f} / {MAX_TOTAL_SCORE:.1f}")


def render_implicit_concerns(implicit_concerns: list) -> None:
    for c in implicit_concerns:
        severity = c.get("severity", "low")
        icon, color = SEVERITY_STYLE.get(severity, ("❓", "gray"))
        category = c.get("category", "other").replace("_", " ").title()
        penalty = c.get("penalty") or 0.0
        st.markdown(
            f"{icon} :{color}[**{severity.upper()}**] · **{category}** `-{penalty:.1f} pts`  \n"
            f"{c.get('description', '')}"
        )
        source = c.get("source", "llm")
        evidence = c.get("evidence")
        if source == "llm" and evidence:
            st.caption(f"“{evidence}”")
        elif source in CONCERN_SOURCE_LABELS:
            st.caption(CONCERN_SOURCE_LABELS[source] + (f" · {evidence}" if source == "salary" and evidence else ""))


@st.cache_data(ttl=60)  # Cache the data for 60 seconds
def load_data(db_path: str = DB_PATH) -> List[dict]:
    if not os.path.exists(db_path):
        return []

    # Opening via JobStateStore ensures legacy databases are migrated with
    # application_status, user_notes, and is_active columns before we query them.
    with JobStateStore(db_path) as store:
        cursor = store.conn.cursor()
        cursor.execute("""
            SELECT job_id, title, company, job_url, recommendation, total_score,
                   evaluation_json, application_status, user_notes, is_active,
                   last_seen_at, evaluator_version
            FROM jobs
            WHERE status = 'EVALUATED'
        """)
        rows = cursor.fetchall()

    jobs = []
    for row in rows:
        job = dict(row)
        try:
            job["evaluation_data"] = json.loads(job["evaluation_json"]) if job.get("evaluation_json") else {}
        except json.JSONDecodeError:
            job["evaluation_data"] = {}

        eval_data = job["evaluation_data"]
        if not job.get("job_id"):
            job["job_id"] = eval_data.get("job_id", "")
        raw_status = (
            job.get("application_status")
            or eval_data.get("application_status")
            or ApplicationStatus.NEW.value
        )
        job["application_status"] = (
            raw_status if raw_status in APPLICATION_STATUSES else ApplicationStatus.NEW.value
        )
        raw_notes = job.get("user_notes")
        if raw_notes is None:
            raw_notes = eval_data.get("user_notes") or ""
        job["user_notes"] = raw_notes
        job["is_active"] = bool(job["is_active"]) if job.get("is_active") is not None else True
        jobs.append(job)

    return jobs


def filter_dashboard_jobs(
    jobs: List[dict],
    selected_statuses: List[str],
    selected_tiers: List[str],
    min_score: float = 0.0,
    show_historical: bool = False,
) -> List[dict]:
    """Filter and sort jobs for the dashboard.

    By default (`show_historical=False`), only active jobs (`is_active == True`)
    from the latest run are shown, except jobs with a user-pinned status
    (`SAVED`, `APPLIED`, `INTERVIEW`, `OFFER`), which are never hidden prematurely.
    """
    filtered = []
    for job in jobs:
        app_status = job.get("application_status", ApplicationStatus.NEW.value)
        is_active = bool(job.get("is_active", True))
        is_pinned = app_status in PINNED_APPLICATION_STATUSES
        if not (show_historical or is_active or is_pinned):
            continue
        if app_status not in selected_statuses:
            continue
        if job.get("recommendation") not in selected_tiers:
            continue
        if (job.get("total_score") or 0) < min_score:
            continue
        filtered.append(job)

    filtered.sort(key=lambda x: x.get("total_score") or 0, reverse=True)
    return filtered


def persist_job_tracking(
    job_id: str,
    application_status: Optional[str] = None,
    user_notes: Optional[str] = None,
    db_path: str = DB_PATH,
) -> bool:
    """Immediately persist status and/or notes to SQLite and invalidate the Streamlit cache."""
    if not job_id or not os.path.exists(db_path):
        return False
    with JobStateStore(db_path) as store:
        updated = store.update_job_tracking(
            job_id=job_id,
            application_status=application_status,
            user_notes=user_notes,
        )
    load_data.clear()
    return updated


def _on_tracking_widget_change(job_id: str, status_key: str, notes_key: str) -> None:
    new_status = st.session_state.get(status_key)
    new_notes = st.session_state.get(notes_key)
    persist_job_tracking(
        job_id=job_id,
        application_status=new_status,
        user_notes=new_notes,
    )


def main():
    st.set_page_config(page_title="Opportunity Engine Dashboard", layout="wide", page_icon="🚀")
    st.title("🚀 Opportunity Engine Dashboard")

    if not os.path.exists(DB_PATH):
        st.error(f"Database not found at `{DB_PATH}`. Please run the pipeline first.")
        return

    jobs = load_data()

    if not jobs:
        st.warning("No evaluated jobs found in the database. The pipeline may not have evaluated any jobs yet.")
        return

    # Sidebar Filters
    st.sidebar.header("Filters")

    show_historical = st.sidebar.toggle(
        "Show expired/historical jobs",
        value=False,
        help="Include cached jobs from older pipeline runs that were not seen in the latest scrape.",
    )

    # Application Status Filter (defaults to active statuses, hiding ARCHIVED unless selected)
    selected_statuses = st.sidebar.multiselect(
        "Application Status",
        options=list(APPLICATION_STATUSES),
        default=list(ACTIVE_APPLICATION_STATUSES),
        format_func=format_status_badge,
    )

    # Recommendation Tier Filter
    all_tiers = ["APPLY", "CONSIDER", "LOW_PRIORITY", "REJECT"]
    default_tiers = ["APPLY", "CONSIDER"]
    selected_tiers = st.sidebar.multiselect(
        "Recommendation Tier",
        options=all_tiers,
        default=default_tiers
    )

    # Minimum Score Filter
    min_score = st.sidebar.slider(
        "Minimum Total Score",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=1.0
    )

    # Filter and sort jobs
    filtered_jobs = filter_dashboard_jobs(
        jobs=jobs,
        selected_statuses=selected_statuses,
        selected_tiers=selected_tiers,
        min_score=min_score,
        show_historical=show_historical,
    )

    st.subheader(f"Showing {len(filtered_jobs)} Job(s)")

    for idx, job in enumerate(filtered_jobs):
        job_id = job.get("job_id") or f"job_{idx}"
        title = job.get("title", "Unknown Title")
        company = job.get("company", "Unknown Company")
        score = job.get("total_score") or 0
        tier = job.get("recommendation", "UNKNOWN")
        url = job.get("job_url", "#")
        app_status = job.get("application_status", ApplicationStatus.NEW.value)
        user_notes = job.get("user_notes") or ""
        is_active = bool(job.get("is_active", True))

        # Color mapping for tiers using Streamlit's colored text syntax
        tier_colors = {
            "APPLY": "green",
            "CONSIDER": "blue",
            "LOW_PRIORITY": "orange",
            "REJECT": "red"
        }
        color = tier_colors.get(tier, "gray")

        status_badge = format_status_badge(app_status)
        expired_badge = "" if is_active else " | ⏳ EXPIRED"
        n_implicit = len(job.get("evaluation_data", {}).get("implicit_concerns", []))
        flag = f" | ⚠️ {n_implicit} implicit concern(s)" if n_implicit else ""
        label = f"{status_badge}{expired_badge} | **{title}** at {company} | Score: **{score:.1f}** | Tier: :{color}[{tier}]{flag}"

        with st.expander(label):
            eval_data = job.get("evaluation_data", {})
            norm_job = eval_data.get("normalized_job", {})

            if not is_active:
                st.caption("⏳ *This listing was not seen in the latest pipeline run and may be expired on the job board.*")

            st.markdown(f"**Company:** {company}")
            if url and url != "#":
                st.markdown(f"**URL:** [View Original Job Posting]({url})")

            salary = norm_job.get("salary")
            if salary:
                st.markdown(f"**Salary:** {salary}")

            # Application Tracking Controls
            status_key = f"app_status_{job_id}"
            notes_key = f"user_notes_{job_id}"
            status_options = list(APPLICATION_STATUSES)
            status_index = status_options.index(app_status) if app_status in status_options else 0

            track_col1, track_col2 = st.columns([1, 2])
            with track_col1:
                new_status = st.selectbox(
                    "Application Status",
                    options=status_options,
                    index=status_index,
                    format_func=format_status_badge,
                    key=status_key,
                    on_change=_on_tracking_widget_change,
                    args=(job_id, status_key, notes_key),
                )
            with track_col2:
                new_notes = st.text_area(
                    "Personal Notes",
                    value=user_notes,
                    placeholder="e.g., Sent CV via LinkedIn, Need to customize cover letter...",
                    height=68,
                    key=notes_key,
                    on_change=_on_tracking_widget_change,
                    args=(job_id, status_key, notes_key),
                )

            if new_status != app_status or new_notes != user_notes:
                persist_job_tracking(
                    job_id=job_id,
                    application_status=new_status,
                    user_notes=new_notes,
                )
                st.rerun()

            st.divider()

            # Display detailed evaluation side-by-side
            col1, col2 = st.columns(2)

            with col1:
                st.write("### Why it matches")
                strong_matches = eval_data.get("strong_matches", [])
                if strong_matches:
                    for match in strong_matches:
                        st.markdown(f"- ✅ {match}")
                else:
                    st.write("*No strong matches listed.*")

                st.write("### Score Breakdown")
                render_score_breakdown(eval_data.get("score_breakdown", {}), score)

            with col2:
                st.write("### Concerns & Penalties")
                concerns = eval_data.get("concerns", [])
                soft_penalties = eval_data.get("soft_penalties", [])
                implicit_concerns = eval_data.get("implicit_concerns", [])
                # Critical implicit concerns are also hard blockers; render them once (with evidence) below.
                hard_blockers = [
                    b for b in eval_data.get("hard_blockers", [])
                    if not b.startswith(IMPLICIT_BLOCKER_PREFIX)
                ]

                has_concerns = False
                if hard_blockers:
                    has_concerns = True
                    for blocker in hard_blockers:
                        st.markdown(f"- ⛔ **Blocker:** {blocker}")
                if implicit_concerns:
                    has_concerns = True
                    st.markdown("#### Implicit Concerns")
                    render_implicit_concerns(implicit_concerns)
                    if soft_penalties or concerns:
                        st.markdown("#### Other Penalties")
                if soft_penalties:
                    has_concerns = True
                    for penalty in soft_penalties:
                        st.markdown(f"- ⚠️ **Penalty:** {penalty}")
                if concerns:
                    has_concerns = True
                    for concern in concerns:
                        st.markdown(f"- ❓ **Concern:** {concern}")

                if not has_concerns:
                    st.write("*No major concerns listed.*")


if __name__ == "__main__":
    main()
