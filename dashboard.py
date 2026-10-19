import streamlit as st
import sqlite3
import json
import os

DB_PATH = ".tmp/state/opportunity_engine.db"

@st.cache_data(ttl=60) # Cache the data for 60 seconds
def load_data():
    if not os.path.exists(DB_PATH):
        return []
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # We fetch jobs with EVALUATED status
    cursor.execute("""
        SELECT title, company, job_url, recommendation, total_score, evaluation_json 
        FROM jobs 
        WHERE status = 'EVALUATED'
    """)
    
    rows = cursor.fetchall()
    jobs = []
    for row in rows:
        job = dict(row)
        try:
            job['evaluation_data'] = json.loads(job['evaluation_json'])
        except json.JSONDecodeError:
            job['evaluation_data'] = {}
        jobs.append(job)
        
    conn.close()
    return jobs

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
    filtered_jobs = [
        job for job in jobs 
        if job.get('recommendation') in selected_tiers 
        and (job.get('total_score') or 0) >= min_score
    ]
    
    filtered_jobs.sort(key=lambda x: x.get('total_score') or 0, reverse=True)
    
    st.subheader(f"Showing {len(filtered_jobs)} Job(s)")
    
    for job in filtered_jobs:
        title = job.get('title', 'Unknown Title')
        company = job.get('company', 'Unknown Company')
        score = job.get('total_score') or 0
        tier = job.get('recommendation', 'UNKNOWN')
        url = job.get('job_url', '#')
        
        # Color mapping for tiers using Streamlit's colored text syntax
        tier_colors = {
            "APPLY": "green",
            "CONSIDER": "blue",
            "LOW_PRIORITY": "orange",
            "REJECT": "red"
        }
        color = tier_colors.get(tier, "gray")
        
        label = f"**{title}** at {company} | Score: **{score:.1f}** | Tier: :{color}[{tier}]"
        
        with st.expander(label):
            eval_data = job.get('evaluation_data', {})
            norm_job = eval_data.get('normalized_job', {})
            
            st.markdown(f"**Company:** {company}")
            if url and url != "#":
                st.markdown(f"**URL:** [View Original Job Posting]({url})")
            
            salary = norm_job.get('salary')
            if salary:
                st.markdown(f"**Salary:** {salary}")
                
            st.divider()
            
            # Display detailed evaluation side-by-side
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("### Why it matches")
                strong_matches = eval_data.get('strong_matches', [])
                if strong_matches:
                    for match in strong_matches:
                        st.markdown(f"- ✅ {match}")
                else:
                    st.write("*No strong matches listed.*")
                    
                st.write("### Score Breakdown")
                breakdown = eval_data.get('score_breakdown', {})
                if breakdown:
                    for k, v in breakdown.items():
                        if k != 'total_score':
                            formatted_key = k.replace('_', ' ').title()
                            st.markdown(f"- **{formatted_key}:** {v}")
                else:
                    st.write("*No score breakdown available.*")
            
            with col2:
                st.write("### Concerns & Penalties")
                concerns = eval_data.get('concerns', [])
                soft_penalties = eval_data.get('soft_penalties', [])
                hard_blockers = eval_data.get('hard_blockers', [])
                
                has_concerns = False
                if hard_blockers:
                    has_concerns = True
                    for blocker in hard_blockers:
                        st.markdown(f"- ⛔ **Blocker:** {blocker}")
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
