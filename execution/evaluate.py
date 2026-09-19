import re
from typing import List, Tuple
from .models import (
    NormalizedJob, CandidateProfile, EvaluationResult, ScoreBreakdown,
    Recommendation, WorkMode, EmploymentType, EvidenceItem, FactType
)


LITHUANIAN_CITIES = [
    "vilnius", "vilniuje", "vilniaus",
    "kaunas", "kaune", "kauno",
    "klaipėda", "klaipėdoje", "klaipėdos", "klaipeda", "klaipedoje",
    "šiauliai", "šiauliuose", "šiaulių", "siauliai", "siauliuose",
    "panevėžys", "panevėžyje", "panevėžio", "panevezys", "panevezyje",
    "alytus", "alytuje", "alytaus",
    "marijampolė", "marijampolėje", "marijampole", "marijampoleje",
    "mažeikiai", "mažeikiuose", "mazeikiai", "mazeikiuose",
    "jonava", "jonavoje",
    "utena", "utenoje",
    "kėdainiai", "kėdainiuose", "kedainiai", "kedainiuose",
    "tauragė", "tauragėje", "taurage", "taurageje",
    "telšiai", "telšiuose", "telsiai", "telsiuose",
    "ukmergė", "ukmergėje", "ukmerge", "ukmergeje",
    "visaginas", "visagine",
    "palanga", "palangoje",
    "plungė", "plungėje", "plunge", "plungeje",
    "lietuva", "lietuvoje", "lithuania", "lithuanian"
]


NON_TECH_TITLE_PATTERNS = [
    r'\baccountant\b', r'\baccounting\b', r'\bauditor\b', r'\baudit\b',
    r'\bbuhalter(?:is|ė|ių)?\b', r'\bapskait(?:ininkas|ininkė|a)?\b',
    r'\bmarketing\b', r'\brinkodara\b', r'\bsales\b',
    r'\bpardavim(?:as|ai|ų|o|ams)?\b', r'\bhr\b', r'\brecruiter\b',
    r'\batrank(?:ų|os)?\b', r'\bpersonalo\b', r'\blegal\b',
    r'\bteisin(?:inkas|ininkė)?\b', r'\bfinance\s+director\b',
    r'\bfinans(?:ų|ai|istas)?\b', r'\bcustomer\s+support\b',
    r'\bklientų\s+aptarnavim', r'\boffice\s+manager\b',
    r'\badministrator(?:ius|ė)?\b', r'\bpatarėjas\b', r'\bbankininkystė\b',
    r'\bpsicholog(?:as|ė|ai)?\b', r'\bpsichoterapeut(?:as|ė|ai)?\b',
    r'\bmedicinos\b', r'\bgydytoj(?:as|ė)?\b', r'\bsveikatos\b',
    r'\bsocialin(?:is|ė)\b'
]

CORE_AI_PATTERNS = [
    r'\bai\b', r'\bdi\b', r'\bdirbtin(?:is|io|į|iame)\s+intelekt(?:as|o|ą|e)\b',
    r'\bmachine\s+learning\b', r'\bml\b', r'\bdeep\s+learning\b',
    r'\bgenai\b', r'\bgenerative\s+ai\b', r'\bllm\b', r'\bnlp\b',
    r'\bcomputer\s+vision\b', r'\bai\s+engineer\b', r'\bai\s+developer\b',
    r'\bprompt\s+engineer\b', r'\bai\s+agent(?:s)?\b', r'\bai\s+consultant\b'
]

AUTOMATION_PATTERNS = [
    r'\bautomation\b', r'\bautomatizavim(?:as|o|ui)?\b', r'\brpa\b',
    r'\bworkflow\s+automation\b', r'\bai\s+automation\b'
]

PYTHON_DATA_PATTERNS = [
    r'\bpython\b', r'\bdata\s+scientist\b', r'\bdata\s+engineer\b',
    r'\bdata\s+analyst\b', r'\bduomenų\s+mokslin(?:inkas|inkė)\b',
    r'\bduomenų\s+analitik(?:as|ė)\b', r'\bduomenų\s+inžinier(?:ius|ė)\b'
]

SENIOR_TITLE_PATTERNS = [
    r'\bsenior\b', r'\blead\b', r'\bprincipal\b', r'\bhead\s+of\b',
    r'\barchitect\b', r'\bdirector\b', r'\bvyresn(?:ysis|ioji|ieji)\b',
    r'\bstaff\b', r'\bekspert(?:as|ė)\b', r'\bexperienced\b'
]

VADOVAS_SENIOR_PATTERNS = [
    r'\b(?:it|tech|departamento|skyriaus|komandos|technologijų|senior)\s+vadov(?:as|ė)\b',
    r'\bhead\b', r'\bchief\b'
]


def _matches_any(patterns: List[str], text: str) -> bool:
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def evaluate_job(job: NormalizedJob, profile: CandidateProfile) -> EvaluationResult:
    """
    Deterministically evaluates a job against the candidate profile based on a 100-point rubric.
    Identifies hard blockers, soft penalties, strong matches, weak matches, missing info, and concerns.
    """
    hard_blockers: List[str] = []
    soft_penalties: List[str] = []
    strong_matches: List[str] = []
    weak_matches: List[str] = []
    missing_info: List[str] = []
    concerns: List[str] = []
    evidence_items: List[EvidenceItem] = list(job.evidence)

    title_lower = job.title.lower()
    text_lower = f"{job.title} {job.description}".lower()

    # 1. AI/ML/Automation Relevance (max 25)
    ai_relevance_pts = 0.0
    is_non_tech = _matches_any(NON_TECH_TITLE_PATTERNS, title_lower)
    is_junior = (
        job.employment_type in [EmploymentType.INTERNSHIP, EmploymentType.WORKING_STUDENT, EmploymentType.ENTRY_LEVEL]
        or any(k in title_lower for k in ["junior", "intern", "praktik", "trainee", "student", "jaunesn"])
    )

    if is_non_tech:
        ai_relevance_pts = 2.0
        concerns.append("Non-technical role outside AI/engineering domain.")
    elif _matches_any(CORE_AI_PATTERNS, title_lower):
        if is_junior:
            ai_relevance_pts = 25.0
            strong_matches.append("Direct AI/ML focus for entry/student level.")
        else:
            ai_relevance_pts = 20.0
            strong_matches.append("Direct AI/ML engineering role.")
    elif _matches_any(CORE_AI_PATTERNS, text_lower) and any(kw in title_lower for kw in ["developer", "engineer", "scientist", "programuotoj", "analyst", "inžinier"]):
        ai_relevance_pts = 18.0
        strong_matches.append("Technical role with substantial AI/ML focus.")
    elif _matches_any(AUTOMATION_PATTERNS, title_lower) or _matches_any(AUTOMATION_PATTERNS, text_lower):
        ai_relevance_pts = 18.0
        strong_matches.append("Automation focus relevant to candidate interests.")
    elif _matches_any(PYTHON_DATA_PATTERNS, title_lower) or ("python" in text_lower and any(kw in title_lower for kw in ["developer", "engineer", "analyst"])):
        ai_relevance_pts = 14.0
        weak_matches.append("Python / Data role with technical adjacency to AI.")
    elif any(re.search(r'\b' + kw + r'\b', title_lower) for kw in ["developer", "engineer", "programuotojas", "programuotoja", "software", "tester", "qa"]):
        ai_relevance_pts = 8.0
        weak_matches.append("General software engineering / IT role.")
    else:
        ai_relevance_pts = 4.0
        concerns.append("Limited direct AI, ML, or automation relevance in listing.")

    # 2. Student / Experience Compatibility (max 20)
    exp_pts = 0.0
    is_senior = _matches_any(SENIOR_TITLE_PATTERNS, title_lower) or (
        bool(re.search(r'\bvadov(?:as|ė)\b', title_lower)) and _matches_any(VADOVAS_SENIOR_PATTERNS, title_lower)
    )
    is_student_friendly = (
        job.employment_type in [EmploymentType.INTERNSHIP, EmploymentType.WORKING_STUDENT]
        or any(k in title_lower for k in ["intern", "praktik", "student", "trainee"])
    )

    if is_senior and not is_student_friendly:
        hard_blockers.append(f"Senior/Lead role ('{job.title}') requires extensive professional experience beyond candidate's student background.")
        evidence_items.append(EvidenceItem(
            fact_type=FactType.FACT,
            statement=f"Role title '{job.title}' specifies Senior/Lead seniority level."
        ))

    if job.experience_is_mandatory and job.min_years_experience >= 2:
        hard_blockers.append(f"Requires {job.min_years_experience}+ years mandatory professional experience.")
        evidence_items.append(EvidenceItem(
            fact_type=FactType.FACT,
            statement=f"Job mandates {job.min_years_experience} years of prior professional experience."
        ))

    if hard_blockers and (is_senior or (job.experience_is_mandatory and job.min_years_experience >= 2)):
        exp_pts = 0.0
    elif job.employment_type in [EmploymentType.INTERNSHIP, EmploymentType.WORKING_STUDENT] or any(k in title_lower for k in ["intern", "praktik", "student", "trainee"]):
        exp_pts = 20.0
        strong_matches.append("Internship / working-student role designed for candidates without prior experience.")
    elif not job.experience_is_mandatory and job.min_years_experience == 1:
        exp_pts = 13.0
        soft_penalties.append("1 year of experience preferred (not mandatory).")
        weak_matches.append("Entry-level role with 1 year preferred experience.")
    elif not job.experience_is_mandatory and job.min_years_experience > 1:
        exp_pts = 8.0
        soft_penalties.append(f"{job.min_years_experience} years of experience preferred.")
        concerns.append(f"Prefers {job.min_years_experience} years experience.")
    elif job.experience_is_mandatory and job.min_years_experience == 1:
        exp_pts = 10.0
        soft_penalties.append("1 year mandatory experience required (Candidate has academic/project experience only).")
        weak_matches.append("Role requires 1 year experience.")
    elif job.employment_type == EmploymentType.ENTRY_LEVEL or "junior" in title_lower or "jaunesn" in title_lower:
        exp_pts = 18.0
        strong_matches.append("Junior / entry-level role suitable for early career.")
    else:
        exp_pts = 6.0
        weak_matches.append("Standard industry role with unstated experience level.")

    # 3. Work Arrangement & Location (max 15)
    loc_pts = 0.0
    loc_lower = job.location.lower()
    is_lt_loc = any(lt_city in loc_lower for lt_city in LITHUANIAN_CITIES)
    
    if job.work_mode == WorkMode.REMOTE:
        loc_pts = 15.0
        strong_matches.append("Fully remote work arrangement available.")
    elif job.work_mode == WorkMode.HYBRID and ("vilnius" in loc_lower or "vilniuje" in loc_lower or "lithuania" in loc_lower or "lietuva" in loc_lower):
        loc_pts = 14.0
        strong_matches.append("Hybrid work mode located in Vilnius.")
    elif job.work_mode == WorkMode.HYBRID and is_lt_loc:
        loc_pts = 11.0
        weak_matches.append(f"Hybrid work mode in {job.location} (Lithuania).")
    elif "vilnius" in loc_lower or "vilniuje" in loc_lower:
        loc_pts = 12.0
        strong_matches.append("On-site location in Vilnius.")
    elif is_lt_loc:
        loc_pts = 6.0
        concerns.append(f"On-site in {job.location} (outside Vilnius, within Lithuania).")
        soft_penalties.append(f"On-site role located outside Vilnius in {job.location}.")
        weak_matches.append(f"Lithuanian location ({job.location}).")
    else:
        if job.work_mode == WorkMode.UNKNOWN:
            loc_pts = 5.0
            missing_info.append("Location / remote work policy not clearly specified.")
        else:
            loc_pts = 0.0
            hard_blockers.append(f"Location '{job.location}' outside Lithuania without remote allowance.")

    # 4. Employment Type & Schedule Compatibility (max 15)
    sched_pts = 0.0
    if job.employment_type == EmploymentType.PART_TIME or "part-time" in text_lower or "dalinis" in text_lower:
        sched_pts = 15.0
        strong_matches.append("Part-time schedule highly compatible with university studies.")
    elif job.employment_type == EmploymentType.WORKING_STUDENT:
        sched_pts = 15.0
        strong_matches.append("Working student arrangement structured around academic studies.")
    elif job.employment_type == EmploymentType.INTERNSHIP or any(k in title_lower for k in ["intern", "praktik", "trainee"]):
        sched_pts = 14.0
        strong_matches.append("Internship position compatible with student schedules.")
    elif job.employment_type == EmploymentType.ENTRY_LEVEL or "junior" in title_lower:
        sched_pts = 7.0
        weak_matches.append("Entry-level role (schedule flexibility should be verified).")
        missing_info.append("Flexibility for university lectures not explicitly stated.")
    elif job.employment_type == EmploymentType.FULL_TIME:
        sched_pts = 5.0
        soft_penalties.append("Full-time position (requires managing university schedule).")
        concerns.append("Full-time schedule may conflict with mandatory university classes.")
    else:
        sched_pts = 6.0
        missing_info.append("Exact employment schedule type not fully defined.")

    # 5. Education Compatibility (max 10)
    edu_pts = 0.0
    if job.degree_is_mandatory:
        edu_pts = 0.0
        hard_blockers.append("Requires completed Bachelor's or Master's degree.")
        evidence_items.append(EvidenceItem(
            fact_type=FactType.FACT,
            statement="Listing mandates a completed higher education degree."
        ))
    elif job.requires_completed_degree and not job.degree_is_mandatory:
        edu_pts = 5.0
        soft_penalties.append("Completed degree is preferred / advantageous.")
        weak_matches.append("Degree is listed as preferred rather than mandatory.")
    elif "student" in text_lower or "studij" in text_lower or is_student_friendly:
        edu_pts = 10.0
        strong_matches.append("Explicitly welcomes university students / ongoing studies.")
    else:
        edu_pts = 6.0
        weak_matches.append("No strict completed degree requirement mentioned.")

    # 6. Technical Skill Overlap based ONLY on known candidate info (max 10)
    # Known candidate facts: 2nd year AI student, foundational AI/ML/Python/Automation
    tech_pts = 0.0
    if is_non_tech:
        tech_pts = 2.0
    else:
        relevant_tech = [t for t in job.technical_keywords if t.lower() in ["python", "ai", "machine learning", "automation", "sql", "git", "pandas", "numpy", "opencv", "pytorch"]]
        if len(relevant_tech) >= 3 or ("python" in title_lower and any(kw in title_lower for kw in ["ai", "machine learning", "ml"])):
            tech_pts = 10.0
            strong_matches.append(f"Core technical stack aligns with 2nd-year AI curriculum.")
        elif len(relevant_tech) >= 1 or "python" in title_lower:
            tech_pts = 7.0
            strong_matches.append("Relevant tools align with foundational AI/Python studies.")
        else:
            tech_pts = 5.0
            missing_info.append("Specific programming libraries not detailed in listing.")

    # 7. Language Compatibility (max 5)
    lang_pts = 5.0
    if "German" in job.language_requirements and "English" not in job.language_requirements:
        lang_pts = 0.0
        hard_blockers.append("Mandatory German language requirement.")
    elif "Russian" in job.language_requirements and ("English" not in job.language_requirements and "Lithuanian" not in job.language_requirements):
        lang_pts = 0.0
        hard_blockers.append("Mandatory Russian language without EN/LT option.")
    else:
        strong_matches.append("Language requirements (Lithuanian / English) match candidate.")

    # Calculate Total Score
    total_score = round(
        ai_relevance_pts + exp_pts + loc_pts + sched_pts + edu_pts + tech_pts + lang_pts, 1
    )

    # Determine Recommendation Tier
    if hard_blockers:
        recommendation = Recommendation.REJECT
        # Heavy penalty on total score if blocked
        total_score = min(total_score, 35.0)
    elif total_score >= 75.0:
        recommendation = Recommendation.APPLY
    elif total_score >= 55.0:
        recommendation = Recommendation.CONSIDER
    elif total_score >= 40.0:
        recommendation = Recommendation.LOW_PRIORITY
    else:
        recommendation = Recommendation.REJECT

    # Add evidence for recommendation
    evidence_items.append(EvidenceItem(
        fact_type=FactType.INFERENCE,
        statement=f"Computed match score {total_score}/100 based on candidate student profile."
    ))
    evidence_items.append(EvidenceItem(
        fact_type=FactType.RECOMMENDATION,
        statement=f"Recommendation: {recommendation.value} (Hard blockers: {len(hard_blockers)}, Soft penalties: {len(soft_penalties)})."
    ))

    # Draft Application Message strictly from verified candidate facts
    draft_msg = None
    if recommendation in [Recommendation.APPLY, Recommendation.CONSIDER]:
        draft_msg = (
            f"Subject: Application for {job.title} - Candidate\n\n"
            f"Dear Hiring Team at {job.company},\n\n"
            f"I am writing to express my strong interest in the {job.title} position. "
            f"I am currently a second-year undergraduate student in Artificial Intelligence in Vilnius. "
            f"I have a strong academic foundation in AI, Machine Learning, and Python programming, "
            f"and I am eager to apply these skills to practical automation and technical challenges at {job.company}.\n\n"
            f"I am fluent in both Lithuanian and English, and I am highly motivated to contribute "
            f"as an energetic learner and team player.\n\n"
            f"Thank you for considering my application. I look forward to the possibility of discussing "
            f"how I can contribute to your team.\n\n"
            f"Best regards,\n[Candidate Name]"
        )

    score_breakdown = ScoreBreakdown(
        ai_relevance=ai_relevance_pts,
        student_compatibility=exp_pts,
        location_compatibility=loc_pts,
        schedule_compatibility=sched_pts,
        education_compatibility=edu_pts,
        technical_skill_overlap=tech_pts,
        language_compatibility=lang_pts,
        total_score=total_score
    )

    return EvaluationResult(
        job_id=job.job_id,
        normalized_job=job,
        score_breakdown=score_breakdown,
        total_score=total_score,
        recommendation=recommendation,
        hard_blockers=hard_blockers,
        soft_penalties=soft_penalties,
        strong_matches=strong_matches,
        weak_matches=weak_matches,
        missing_information=missing_info,
        concerns=concerns,
        evidence_items=evidence_items,
        application_message_draft=draft_msg
    )
