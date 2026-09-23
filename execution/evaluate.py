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

NON_TECH_STRICT_PATTERNS = [
    r'\baccountant\b', r'\baccounting\b', r'\bauditor\b', r'\baudit\b',
    r'\bbuhalter(?:is|ė|ių)?\b', r'\bapskait(?:ininkas|ininkė|a)?\b',
    r'\bmarketing\b', r'\brinkodara\b', r'\bsales\b',
    r'\bpardavim(?:as|ai|ų|o|ams)?\b', r'\bhr\b', r'\brecruiter\b',
    r'\batrank(?:ų|os)?\b', r'\bpersonalo\b', r'\blegal\b',
    r'\bteisin(?:inkas|ininkė)?\b', r'\bfinance\s+director\b',
    r'\bfinans(?:ų|ai|istas)?\b', r'\bcustomer\s+support\b',
    r'\bklientų\s+aptarnavim', r'\bklientų\s+aktyvavim', r'\boffice\s+manager\b',
    r'\badministrator(?:ius|ė)?\b', r'\bpatarėjas\b', r'\bbankininkystė\b',
    r'\bpsicholog(?:as|ė|ai)?\b', r'\bpsichoterapeut(?:as|ė|ai)?\b',
    r'\bmedicinos\b', r'\bgydytoj(?:as|ė)?\b', r'\bsveikatos\b',
    r'\bsocialin(?:is|ė)\b', r'\bbendrųjų\s+reikalų\b',
    r'\borganizacijos\s+vystym', r'\bugdymo\s+grup', r'\braštin(?:ė|ininkas)',
    r'\bsandėli(?:o|ininkas|ninkė)\b', r'\blogistik(?:os|as)?\b',
    r'\bkurjer(?:is|ė)\b', r'\bvadybinink(?:as|ė)\b',
    r'\bpaskolų\b', r'\bkreditų\b', r'\bdraudimo\b'
]

BROAD_BUSINESS_PATTERNS = [
    r'\bbusiness\s+development\b', r'\bverslo\s+vystym',
    r'\binnovation\s+&\s+business\s+excellence\b',
    r'\boperations\b', r'\boperacijų\b',
    r'\bprojektų\s+valdym', r'\bproject\s+management\b',
    r'\bstartup\s+lithuania\b', r'\bkomunikacij(?:os|ų)\b',
    r'\berp/business\s+applications\b'
]

TECH_TITLE_INDICATORS = [
    r'\bdeveloper\b', r'\bengineer\b', r'\bscientist\b', r'\bprogramuotoj',
    r'\binžinier', r'\barchitect\b', r'\bdata\b', r'\banalyst\b',
    r'\bsoftware\b', r'\btechnolog\b'
]

TECH_DESCRIPTION_INDICATORS = [
    r'\bpython\b', r'\bc\+\+\b', r'\bjava\b', r'\bsql\b', r'\bmachine\s+learning\b',
    r'\bdeep\s+learning\b', r'\balgorithms\b', r'\bprogramming\b', r'\bcoding\b',
    r'\bgit\b', r'\bdata\s+pipeline\b', r'\bneural\b', r'\bautomati'
]

CORE_AI_PATTERNS = [
    r'\bai\b', r'\bdi\b', r'\bdirbtin(?:is|io|į|iame)\s+intelekt(?:as|o|ą|e)\b',
    r'\bmachine\s+learning\b', r'\bml\b', r'\bdeep\s+learning\b',
    r'\bgenai\b', r'\bgenerative\s+ai\b', r'\bllm\b', r'\bllms\b',
    r'\bnlp\b', r'\bnatural\s+language\b', r'\bcomputer\s+vision\b',
    r'\bai\s+engineer(?:ing)?\b', r'\bai\s+developer\b',
    r'\bprompt\s+engineer\b', r'\bai\s+agent(?:s)?\b', r'\bagentic\b',
    r'\bautonomous\s+agent(?:s)?\b', r'\bai\s+automation\b'
]

AUTOMATION_PATTERNS = [
    r'\bautomation\b', r'\bautomatizavim(?:as|o|ui)?\b', r'\brpa\b',
    r'\bworkflow\s+automation\b', r'\bprocess\s+automation\b'
]

PYTHON_DATA_PATTERNS = [
    r'\bpython\b', r'\bdata\s+scientist\b', r'\bdata\s+engineer\b',
    r'\bdata\s+analyst\b', r'\bduomenų\s+mokslin(?:inkas|inkė)\b',
    r'\bduomenų\s+analitik(?:as|ė)\b', r'\bduomenų\s+inžinier(?:ius|ė)\b',
    r'\bdata\s+science\b'
]

GENERIC_SOFTWARE_PATTERNS = [
    r'\bdeveloper\b', r'\bengineer\b', r'\bprogramuotoj(?:as|a|ai)?\b',
    r'\bsoftware\b', r'\bfrontend\b', r'\bfront-end\b', r'\bbackend\b',
    r'\bback-end\b', r'\bfull-stack\b', r'\bfullstack\b', r'\bweb\b',
    r'\bjava\b', r'\bc#\b', r'\b\.net\b', r'\bphp\b', r'\breact\b',
    r'\bangular\b', r'\bvue\b', r'\bnode\b', r'\bqa\b', r'\btester\b',
    r'\btesting\b', r'\btestuotoj(?:as|a)?\b'
]

IT_SUPPORT_PATTERNS = [
    r'\bhelpdesk\b', r'\bit\s+support\b', r'\btechnin(?:is|ė)\s+pagalba\b',
    r'\bpagalbos\s+specialist(?:as|ė)\b', r'\btinklo\s+administrator(?:ius|ė)?\b',
    r'\bsystem\s+administrator\b', r'\bsistemų\s+administrator(?:ius|ė)?\b',
    r'\bhardware\b'
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

CANDIDATE_SKILL_GROUPS = {
    "python": [r'\bpython\b', r'\bpy\b'],
    "c_cpp": [r'\bc\+\+\b', r'\bcpp\b', r'\bc\s+and\s+c\+\+\b'],
    "ai_ml": [
        r'\bmachine\s+learning\b', r'\bml\b', r'\bdeep\s+learning\b',
        r'\bdirbtin(?:is|io|į|iame)\s+intelekt(?:as|o|ą|e)\b', r'\bai\b'
    ],
    "genai_llm": [
        r'\bllm\b', r'\bllms\b', r'\bgenai\b', r'\bgenerative\s+ai\b',
        r'\bprompt\b', r'\btransformers?\b'
    ],
    "ai_agents": [
        r'\bai\s+agent(?:s)?\b', r'\bagentic\b', r'\bautonomous\s+agents?\b',
        r'\blangchain\b', r'\bcrewai\b'
    ],
    "automation": [
        r'\bautomation\b', r'\bautomatizavim(?:as|o|ui)?\b', r'\brpa\b',
        r'\bworkflow\b'
    ],
    "cs_foundations": [
        r'\boop\b', r'\bobject-oriented\b', r'\bdata\s+structures?\b',
        r'\balgorithms?\b', r'\bduomenų\s+struktūr', r'\balgoritm', r'\brecursion\b'
    ],
    "tools": [
        r'\bgit\b', r'\bgithub\b', r'\blinux\b', r'\bwsl\b', r'\bmatlab\b'
    ]
}


def _matches_any(patterns: List[str], text: str) -> bool:
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def evaluate_job(job: NormalizedJob, profile: CandidateProfile) -> EvaluationResult:
    """
    Deterministically evaluates a job against the candidate profile based on a calibrated 100-point model:
    - Role/Domain Relevance: 40 points
    - Technical Skill Overlap: 15 points
    - Experience/Student Compatibility: 20 points
    - Schedule Compatibility: 10 points
    - Location/Work Mode: 10 points
    - Language Compatibility: 5 points

    AI/domain + technical overlap account for 55% of the total score.
    APPLY gate requires total_score >= 75.0 AND ai_relevance >= 26.0.
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

    # Identify if the role is student/junior oriented
    is_junior = (
        job.employment_type in [EmploymentType.INTERNSHIP, EmploymentType.WORKING_STUDENT, EmploymentType.ENTRY_LEVEL]
        or any(k in title_lower for k in ["junior", "intern", "praktik", "trainee", "student", "jaunesn"])
    )

    # ---------------------------------------------------------
    # Non-Technical & Out-of-Scope Detection
    # ---------------------------------------------------------
    has_tech_title = _matches_any(TECH_TITLE_INDICATORS, title_lower)
    has_tech_desc = _matches_any(TECH_DESCRIPTION_INDICATORS, text_lower)

    is_strict_non_tech = _matches_any(NON_TECH_STRICT_PATTERNS, title_lower) and not has_tech_title
    is_broad_business_non_tech = _matches_any(BROAD_BUSINESS_PATTERNS, title_lower) and not has_tech_title and not has_tech_desc

    is_non_tech = is_strict_non_tech or is_broad_business_non_tech
    is_it_support = _matches_any(IT_SUPPORT_PATTERNS, title_lower) and not has_tech_desc

    # ---------------------------------------------------------
    # 1. Role / Domain Relevance (Max 40.0 pts)
    # ---------------------------------------------------------
    ai_relevance_pts = 0.0

    if is_non_tech:
        ai_relevance_pts = 0.0
        concerns.append("Non-technical role outside AI, software, and data engineering domains.")
        hard_blockers.append(f"Role '{job.title}' is a non-technical role outside the candidate's career direction.")
    elif is_it_support:
        ai_relevance_pts = 4.0
        concerns.append("IT support / helpdesk role with limited development or AI relevance.")
    elif _matches_any(CORE_AI_PATTERNS, title_lower):
        # Direct AI/ML in title
        if has_tech_desc or is_junior:
            ai_relevance_pts = 40.0 if is_junior else 36.0
            strong_matches.append("Primary career direction: Direct AI/ML/GenAI engineering focus.")
        else:
            ai_relevance_pts = 26.0
            concerns.append("Title mentions AI but description indicates limited technical AI engineering tasks.")
    elif _matches_any(CORE_AI_PATTERNS, text_lower) and has_tech_title:
        # Substantial AI/ML in description for a technical role
        ai_relevance_pts = 35.0 if is_junior else 32.0
        strong_matches.append("Primary career direction: Technical role with substantial AI/ML/GenAI focus in responsibilities.")
    elif _matches_any(AUTOMATION_PATTERNS, title_lower) or (_matches_any(AUTOMATION_PATTERNS, text_lower) and has_tech_title):
        # Automation focus
        if "python" in text_lower or _matches_any(CORE_AI_PATTERNS, text_lower):
            ai_relevance_pts = 30.0 if is_junior else 28.0
            strong_matches.append("Strong adjacent direction: Python and workflow automation focus.")
        else:
            ai_relevance_pts = 25.0
            strong_matches.append("Automation focus relevant to candidate interests.")
    elif _matches_any(PYTHON_DATA_PATTERNS, title_lower) or ("python" in text_lower and has_tech_title):
        # Python / Data role
        if any(kw in text_lower for kw in ["machine learning", "ai", "deep learning", "automation", "pipeline"]):
            ai_relevance_pts = 26.0 if is_junior else 24.0
            strong_matches.append("Strong adjacent direction: Data science and engineering with ML/automation context.")
        else:
            ai_relevance_pts = 22.0
            weak_matches.append("Adjacent direction: Python development foundations.")
    elif any(kw in text_lower for kw in ["c++", "cpp"]) and has_tech_title:
        # C/C++ technical role
        ai_relevance_pts = 18.0
        weak_matches.append("Adjacent direction: C/C++ foundational systems programming.")
    elif _matches_any(GENERIC_SOFTWARE_PATTERNS, title_lower):
        # Generic software engineering
        if any(kw in text_lower for kw in ["data", "automation", "python", "pipeline", "machine learning"]):
            ai_relevance_pts = 16.0
            weak_matches.append("General software role with some data/automation/Python responsibilities.")
        else:
            ai_relevance_pts = 10.0
            concerns.append("Generic software engineering role with no direct AI/data/automation connection.")
    else:
        ai_relevance_pts = 5.0
        concerns.append("Limited technical or AI relevance identified in listing.")

    # ---------------------------------------------------------
    # 2. Technical Skill Overlap (Max 15.0 pts)
    # Evaluates verified skills from candidate profile
    # ---------------------------------------------------------
    tech_pts = 0.0

    if is_non_tech:
        tech_pts = 0.0
    else:
        matched_groups = 0
        for group_name, patterns in CANDIDATE_SKILL_GROUPS.items():
            if _matches_any(patterns, text_lower) or any(_matches_any(patterns, kw.lower()) for kw in job.technical_keywords):
                matched_groups += 1

        if matched_groups >= 4:
            tech_pts = 15.0
            strong_matches.append("Strong technical overlap with candidate's verified skills (Python, AI/ML, CS foundations, Git/Linux).")
        elif matched_groups == 3:
            tech_pts = 12.0
            strong_matches.append("Substantial technical skill overlap with candidate profile.")
        elif matched_groups == 2:
            tech_pts = 9.0
            weak_matches.append("Moderate technical skill overlap with candidate foundations.")
        elif matched_groups == 1:
            tech_pts = 6.0
            weak_matches.append("Basic technical skill overlap with candidate foundations.")
        else:
            # Check if listing lacks tool details or requires entirely disjoint stack
            if not job.technical_keywords and not has_tech_desc:
                tech_pts = 5.0
                missing_info.append("Specific programming languages or technical tools not detailed in listing.")
            else:
                tech_pts = 2.0
                concerns.append("Required tech stack does not match candidate's current technical foundations.")

    # ---------------------------------------------------------
    # 3. Experience / Student Compatibility (Max 20.0 pts)
    # ---------------------------------------------------------
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

    # Mandatory completed degree check
    if job.degree_is_mandatory:
        hard_blockers.append("Requires completed Bachelor's or Master's degree.")
        evidence_items.append(EvidenceItem(
            fact_type=FactType.FACT,
            statement="Listing mandates a completed higher education degree."
        ))

    if hard_blockers and (is_senior or (job.experience_is_mandatory and job.min_years_experience >= 2) or job.degree_is_mandatory or is_non_tech):
        exp_pts = 0.0
    elif is_student_friendly:
        exp_pts = 20.0
        strong_matches.append("Internship / working-student role designed for candidates without prior experience.")
    elif not job.experience_is_mandatory and job.min_years_experience == 1:
        exp_pts = 14.0
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
        exp_pts = 7.0
        missing_info.append("Exact experience level not explicitly stated in listing.")

    # Soft deduction if completed degree is preferred (not mandatory)
    if job.requires_completed_degree and not job.degree_is_mandatory:
        exp_pts = max(0.0, exp_pts - 3.0)
        soft_penalties.append("Completed degree is preferred / advantageous.")

    if "student" in text_lower or "studij" in text_lower or is_student_friendly:
        strong_matches.append("Explicitly welcomes university students / ongoing studies.")

    # ---------------------------------------------------------
    # 4. Schedule Compatibility (Max 10.0 pts)
    # ---------------------------------------------------------
    sched_pts = 0.0

    if job.employment_type == EmploymentType.PART_TIME or "part-time" in text_lower or "dalinis" in text_lower:
        sched_pts = 10.0
        strong_matches.append("Part-time schedule highly compatible with university studies.")
    elif job.employment_type == EmploymentType.WORKING_STUDENT:
        sched_pts = 10.0
        strong_matches.append("Working student arrangement structured around academic studies.")
    elif job.employment_type == EmploymentType.INTERNSHIP or any(k in title_lower for k in ["intern", "praktik", "trainee"]):
        sched_pts = 9.0
        strong_matches.append("Internship schedule structured for students.")
    elif job.employment_type == EmploymentType.ENTRY_LEVEL or "junior" in title_lower:
        sched_pts = 5.0
        missing_info.append("Flexibility for university lectures not explicitly stated.")
    elif job.employment_type == EmploymentType.FULL_TIME:
        sched_pts = 3.0
        soft_penalties.append("Full-time position (requires managing university schedule).")
        concerns.append("Full-time schedule may conflict with mandatory university classes.")
    else:
        sched_pts = 5.0
        missing_info.append("Exact employment schedule type not fully defined.")

    # ---------------------------------------------------------
    # 5. Location / Work Mode (Max 10.0 pts)
    # ---------------------------------------------------------
    loc_pts = 0.0
    loc_lower = job.location.lower()
    is_lt_loc = any(lt_city in loc_lower for lt_city in LITHUANIAN_CITIES)

    if job.work_mode == WorkMode.REMOTE:
        loc_pts = 10.0
        strong_matches.append("Fully remote work arrangement available.")
    elif job.work_mode == WorkMode.HYBRID and ("vilnius" in loc_lower or "vilniuje" in loc_lower or "lithuania" in loc_lower or "lietuva" in loc_lower):
        loc_pts = 9.0
        strong_matches.append("Hybrid work mode located in Vilnius.")
    elif "vilnius" in loc_lower or "vilniuje" in loc_lower:
        loc_pts = 8.0
        strong_matches.append("On-site location in Vilnius.")
    elif job.work_mode == WorkMode.HYBRID and is_lt_loc:
        loc_pts = 6.0
        weak_matches.append(f"Hybrid work mode in {job.location} (Lithuania).")
    elif is_lt_loc:
        loc_pts = 4.0
        concerns.append(f"On-site in {job.location} (outside Vilnius, within Lithuania).")
        soft_penalties.append(f"On-site role located outside Vilnius in {job.location}.")
    else:
        if job.work_mode == WorkMode.UNKNOWN:
            loc_pts = 4.0
            missing_info.append("Location / remote work policy not clearly specified.")
        else:
            loc_pts = 0.0
            hard_blockers.append(f"Location '{job.location}' outside Lithuania without remote allowance.")

    # ---------------------------------------------------------
    # 6. Language Compatibility (Max 5.0 pts)
    # ---------------------------------------------------------
    lang_pts = 5.0
    if "German" in job.language_requirements and "English" not in job.language_requirements:
        lang_pts = 0.0
        hard_blockers.append("Mandatory German language requirement.")
    elif "Russian" in job.language_requirements and ("English" not in job.language_requirements and "Lithuanian" not in job.language_requirements):
        lang_pts = 0.0
        hard_blockers.append("Mandatory Russian language without EN/LT option.")
    else:
        strong_matches.append("Language requirements (Lithuanian / English) match candidate.")

    # ---------------------------------------------------------
    # Calculate Total Score & Recommendation
    # ---------------------------------------------------------
    raw_total = ai_relevance_pts + tech_pts + exp_pts + sched_pts + loc_pts + lang_pts
    total_score = round(raw_total, 1)

    # Determine Recommendation Tier
    if hard_blockers or is_non_tech:
        recommendation = Recommendation.REJECT
        total_score = min(total_score, 25.0 if is_non_tech else 35.0)
    elif total_score >= 75.0:
        # APPLY Gate: Role must genuinely represent primary AI or strong AI-adjacent direction
        if ai_relevance_pts >= 26.0:
            recommendation = Recommendation.APPLY
        else:
            recommendation = Recommendation.CONSIDER
            weak_matches.append(
                f"High overall compatibility score ({total_score}/100), but role lacks primary AI/automation domain focus (Domain score: {ai_relevance_pts}/40). Recommended as CONSIDER."
            )
    elif total_score >= 55.0:
        recommendation = Recommendation.CONSIDER
    elif total_score >= 40.0:
        recommendation = Recommendation.LOW_PRIORITY
    else:
        recommendation = Recommendation.REJECT

    # Add evidence for recommendation
    evidence_items.append(EvidenceItem(
        fact_type=FactType.INFERENCE,
        statement=f"Computed match score {total_score}/100 based on candidate AI student profile."
    ))
    evidence_items.append(EvidenceItem(
        fact_type=FactType.RECOMMENDATION,
        statement=f"Recommendation: {recommendation.value} (Hard blockers: {len(hard_blockers)}, Soft penalties: {len(soft_penalties)})."
    ))

    # Draft Application Message strictly grounded in verified candidate facts
    draft_msg = None
    if recommendation in [Recommendation.APPLY, Recommendation.CONSIDER]:
        draft_msg = (
            f"Subject: Application for {job.title} - Nedas Gelumbeckas\n\n"
            f"Dear Hiring Team at {job.company},\n\n"
            f"I am writing to express my strong interest in the {job.title} position. "
            f"I am currently a second-year undergraduate student in Artificial Intelligence at VILNIUS TECH in Vilnius, "
            f"seeking my first professional technical opportunity alongside my studies.\n\n"
            f"My academic foundation includes AI and machine learning fundamentals, Python programming, "
            f"C/C++, object-oriented programming, data structures, and algorithms. In addition to my coursework, "
            f"I am actively developing 'Opportunity Engine', an AI-based personal project for automated, "
            f"evidence-grounded job opportunity discovery and deterministic evaluation. This project has given me "
            f"hands-on experience with Python automation, structured data processing, and agentic workflows.\n\n"
            f"I am fluent in both Lithuanian and English, highly eager to learn, and motivated to contribute "
            f"meaningfully to technical and automation challenges at {job.company}.\n\n"
            f"Thank you for considering my application. I look forward to the possibility of discussing "
            f"how I can support your team.\n\n"
            f"Best regards,\nNedas Gelumbeckas"
        )

    score_breakdown = ScoreBreakdown(
        ai_relevance=ai_relevance_pts,
        student_compatibility=exp_pts,
        location_compatibility=loc_pts,
        schedule_compatibility=sched_pts,
        education_compatibility=0.0,
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
