import re
import hashlib
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from typing import List, Tuple, Optional
from .models import (
    RawJobListing, NormalizedJob, WorkMode, EmploymentType, EvidenceItem, FactType
)


def clean_url(url: Optional[str]) -> Optional[str]:
    """Strips tracking query parameters (UTM, etc.) and validates URL structure."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return None
    try:
        parsed = urlparse(url)
        # Keep non-tracking query parameters
        filtered_queries = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in {"ref", "source", "fbclid", "gclid"}
        ]
        clean_query = urlencode(filtered_queries)
        clean_parsed = parsed._replace(query=clean_query, fragment="")
        return urlunparse(clean_parsed)
    except Exception:
        return url


def normalize_company(name: str) -> str:
    """
    Normalizes company entity names for cross-source matching and deduplication.
    Removes corporate legal suffixes, entity grouping noise, punctuation,
    and maps known brand aliases (e.g., 'Ignitis grupė' -> 'ignitis', 'Ernst & Young' -> 'ey').
    """
    if not name or not isinstance(name, str):
        return ""
    c = name.lower()
    c = c.replace("&", " and ")
    c = re.sub(r'[\"\'„“”‘’`\(\)\[\]\{\}\<\>\,\.\;\:\-\–\—\_\/\\\|\*\+\@]', ' ', c)
    tokens = [t for t in re.split(r'\s+', c) if t]
    legal_forms = {
        'uab', 'ab', 'mb', 'vsi', 'všį', 'ii', 'iį', 'tub', 'tūb', 'kub', 'kūb',
        'inc', 'incorporated', 'llc', 'ltd', 'limited', 'corp', 'corporation',
        'gmbh', 'ag', 'sa', 'sas', 'oy', 'as', 'plc', 'co', 'company',
        'sia', 'ou', 'oü', 'spzoo'
    }
    entity_noise = {'group', 'grupė', 'grupe', 'holding', 'holdings'}
    noise = legal_forms | entity_noise
    filtered = [t for t in tokens if t not in noise]
    if not filtered:
        filtered = tokens
    geo_tokens = {'lietuva', 'lithuania', 'baltic', 'baltics'}
    if len(filtered) > 1 and filtered[-1] in geo_tokens and len(''.join(filtered[:-1])) >= 3:
        filtered = filtered[:-1]
    res = ' '.join(filtered)
    brand_map = {
        'ernst and young': 'ey',
        'ernst young': 'ey',
        'ey baltic': 'ey',
        'ey baltics': 'ey',
        'ey lithuania': 'ey',
        'ey lietuva': 'ey',
        'pwc': 'pwc',
        'pricewaterhousecoopers': 'pwc',
        'kpmg baltics': 'kpmg',
        'kpmg lietuva': 'kpmg',
    }
    return brand_map.get(res, res)


def normalize_title(title: str) -> str:
    """Normalizes title string for deduplication and matching."""
    t = title.lower()
    # Strip gender/diversity neutrality tags like (F/M/D), [m/f/d], (m/w/d), (f/m/x), (gn), (all genders), etc.
    t = re.sub(r'\(\s*[fmdwx\s\/\\]+\s*\)', ' ', t)
    t = re.sub(r'\[\s*[fmdwx\s\/\\]+\s*\]', ' ', t)
    t = re.sub(r'\b[fmdwx]\s*[\/\\]\s*[fmdwx](?:\s*[\/\\]\s*[fmdwx])?\b', ' ', t)
    t = re.sub(r'\(\s*(?:all\s+genders|gn)\s*\)', ' ', t)
    # Standardize & to and
    t = t.replace('&', ' and ')
    # Clean punctuation and brackets
    t = re.sub(r'[\(\)\[\]\{\}\/\\,\-\–\—\|\:\;\.\"\”\“\’\'\`\•\·\*\~]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


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


def detect_work_mode(text: str, location_raw: str) -> WorkMode:
    combined = f"{text} {location_raw}".lower()
    
    if any(k in combined for k in [
        "remote", "nuotolinis", "nuotoliu", "darbas iš namų", "work from home", "100% remote", "fully remote"
    ]):
        if any(k in combined for k in ["hybrid", "hibridinis", "hibridas"]):
            return WorkMode.HYBRID
        return WorkMode.REMOTE
    
    if any(k in combined for k in ["hybrid", "hibridinis", "hibridas", "dalinai nuotolinis"]):
        return WorkMode.HYBRID
    
    onsite_indicators = ["on-site", "onsite", "biure", "ofise", "darbo vieta"] + LITHUANIAN_CITIES
    if any(k in combined for k in onsite_indicators):
        return WorkMode.ONSITE
    
    return WorkMode.UNKNOWN


def _matches_any_pattern(text: str, patterns: List[str]) -> bool:
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def detect_employment_type(text: str, title: str) -> EmploymentType:
    """
    Detects employment type with strict title-first priority.
    Prevents senior roles from being classified as entry-level/internship due to
    mentoring duties or past-experience mentions in description boilerplate.
    """
    title_lower = title.lower()

    # 0. Senior / Lead titles are NEVER internships or entry-level roles
    senior_title_patterns = [
        r'\bsenior\b', r'\blead\b', r'\bprincipal\b', r'\bhead\s+of\b',
        r'\barchitect\b', r'\bdirector\b', r'\bvyresn(?:ysis|ioji|ieji)\b',
        r'\bstaff\b', r'\bekspert(?:as|ė)\b'
    ]
    if _matches_any_pattern(title_lower, senior_title_patterns):
        if _matches_any_pattern(title_lower, [r'\bpart[\-\s]time\b', r'\bpus(?:ė|e)\s+etato\b']):
            return EmploymentType.PART_TIME
        return EmploymentType.FULL_TIME

    # 1. Title-first checks (highest confidence)
    intern_title_patterns = [
        r'\bintern(?:ship|ships|s)?\b',
        r'\bpraktik(?:a|os|ai|ą|oje|ant[a-ząčęėįšųū]*)\b',
        r'\btrainee(?:s)?\b',
        r'\bstažuot(?:ė|ės|ei|ę|ėje|ojas|ojai|otojas)?\b',
        r'\bstudent\s+internship\b'
    ]
    if _matches_any_pattern(title_lower, intern_title_patterns):
        return EmploymentType.INTERNSHIP

    working_student_title_patterns = [
        r'\bworking\s+student\b',
        r'\bstudentas\b',
        r'\bstudentams\b',
        r'\bstudent\s+role\b'
    ]
    if _matches_any_pattern(title_lower, working_student_title_patterns):
        return EmploymentType.WORKING_STUDENT

    part_time_title_patterns = [
        r'\bpart[\-\s]time\b',
        r'\bpus(?:ė|e)\s+etato\b',
        r'\b0\.5\s+etato\b',
        r'\bdalinis\s+etatas\b'
    ]
    if _matches_any_pattern(title_lower, part_time_title_patterns):
        return EmploymentType.PART_TIME

    junior_title_patterns = [
        r'\bjunior\b',
        r'\bjaunesnysis\b',
        r'\bjaunesnioji\b',
        r'\bentry[\-\s]level\b',
        r'\bpradedant(?:iesiems|ysis)?\b'
    ]
    if _matches_any_pattern(title_lower, junior_title_patterns):
        return EmploymentType.ENTRY_LEVEL

    full_time_title_patterns = [
        r'\bfull[\-\s]time\b',
        r'\bpilnas\s+etatas\b',
        r'\bvisas\s+etatas\b',
        r'\b1\.0\s+etatas\b'
    ]
    if _matches_any_pattern(title_lower, full_time_title_patterns):
        return EmploymentType.FULL_TIME

    # 2. Description-level fallback with strict context guards
    # (Guarded against "mentor junior", "personal projects, internships", etc.)
    intern_desc_patterns = [
        r'\b(?:this|the)\s+internship\b',
        r'\binternship\s+(?:position|programme|program|role|opportunity|duration)\b',
        r'\bpraktikos\s+(?:vieta|pozicija|programa)\b',
        r'\bieškom(?:as|a)\s+praktikant(?:as|ė)\b',
        r'\bstudent\s+internship\b',
        r'\bsiūlome\s+praktiką\b'
    ]
    if _matches_any_pattern(text, intern_desc_patterns):
        return EmploymentType.INTERNSHIP

    working_student_desc_patterns = [
        r'\bworking\s+student\b',
        r'\bstudentams\s+(?:siūlome|darbas)\b'
    ]
    if _matches_any_pattern(text, working_student_desc_patterns):
        return EmploymentType.WORKING_STUDENT

    if _matches_any_pattern(text, part_time_title_patterns):
        return EmploymentType.PART_TIME

    junior_desc_patterns = [
        r'\bentry[\-\s]level\s+(?:position|role|candidate|opportunity)\b',
        r'\bpradedantiesiems\s+(?:siūlome|darbas|specialistams)\b'
    ]
    if _matches_any_pattern(text, junior_desc_patterns):
        return EmploymentType.ENTRY_LEVEL

    if _matches_any_pattern(text, full_time_title_patterns):
        return EmploymentType.FULL_TIME

    return EmploymentType.UNKNOWN


def extract_education_rules(text: str) -> Tuple[Optional[str], bool, bool]:
    """
    Returns: (education_description, requires_completed_degree, degree_is_mandatory)
    """
    lower = text.lower()
    
    # Check for student friendly statements
    student_signals = [
        "student", "studijuojant", "university student", "currently pursuing",
        "2-4 kurso", "studentams", "studijos", "degree in progress"
    ]
    if any(s in lower for s in student_signals):
        return ("University student / studies in progress accepted", False, False)
        
    # Check for mandatory completed degree
    mandatory_degree_patterns = [
        r"completed\s+(?:bachelor|master|degree)",
        r"(?:bachelor|master|b\.s\.|m\.s\.)\s*(?:degree)?\s*(?:is\s*)?required",
        r"aukštasis\s+(?:universitetinis\s+)?išsilavinimas\s*\((?:baigtas|būtinas)\)",
        r"turėti\s+(?:aukštąjį|bakalauro|magistro)",
        r"bachelor'?s\s+degree\s+required",
        r"privaloma\s*:\s*aukštasis"
    ]
    for pat in mandatory_degree_patterns:
        if re.search(pat, lower):
            return ("Completed Bachelor's / Master's degree mandatory", True, True)
            
    # Check for preferred degree
    preferred_degree_patterns = [
        r"(?:bachelor|master|degree)\s+(?:is\s+)?preferred",
        r"(?:bachelor|master|degree)\s+is\s+a\s+plus",
        r"išsilavinimas\s*-\s*privalumas",
        r"aukštasis\s+išsilavinimas\s+\(privalumas\)"
    ]
    for pat in preferred_degree_patterns:
        if re.search(pat, lower):
            return ("Degree preferred / advantageous", True, False)
            
    # General mention of degree / field of study without hard requirement
    if any(d in lower for d in ["degree in computer science", "degree in ai", "išsilavinimas tiksliųjų"]):
        return ("Degree in relevant field mentioned", False, False)
        
    return (None, False, False)


def normalize_location(location: str) -> str:
    """Normalizes location string by removing work mode annotations and punctuation."""
    if not location:
        return "Unknown"
    loc = location.lower()
    loc = re.sub(r'\([^\)]*\)', '', loc)  # Remove (Hybrid), (Remote), etc.
    loc = re.sub(r'[\,\-\|\/]', ' ', loc)
    loc = re.sub(r'\s+', ' ', loc).strip()
    if not loc:
        return "Unknown"

    city_canonical_map = {
        "vilnius": "Vilnius", "vilniuje": "Vilnius", "vilniaus": "Vilnius",
        "kaunas": "Kaunas", "kaune": "Kaunas", "kauno": "Kaunas",
        "klaipėda": "Klaipėda", "klaipėdoje": "Klaipėda", "klaipėdos": "Klaipėda",
        "klaipeda": "Klaipėda", "klaipedoje": "Klaipėda",
        "šiauliai": "Šiauliai", "šiauliuose": "Šiauliai", "šiaulių": "Šiauliai",
        "siauliai": "Šiauliai", "siauliuose": "Šiauliai",
        "panevėžys": "Panevėžys", "panevėžyje": "Panevėžys", "panevėžio": "Panevėžys",
        "panevezys": "Panevėžys", "panevezyje": "Panevėžys",
        "alytus": "Alytus", "alytuje": "Alytus", "alytaus": "Alytus",
        "marijampolė": "Marijampolė", "marijampolėje": "Marijampolė",
        "marijampole": "Marijampolė", "marijampoleje": "Marijampolė",
        "mažeikiai": "Mažeikiai", "mažeikiuose": "Mažeikiai",
        "mazeikiai": "Mažeikiai", "mazeikiuose": "Mažeikiai",
        "jonava": "Jonava", "jonavoje": "Jonava",
        "utena": "Utena", "utenoje": "Utena",
        "kėdainiai": "Kėdainiai", "kėdainiuose": "Kėdainiai",
        "kedainiai": "Kėdainiai", "kedainiuose": "Kėdainiai",
        "tauragė": "Tauragė", "tauragėje": "Tauragė",
        "taurage": "Tauragė", "taurageje": "Tauragė",
        "telšiai": "Telšiai", "telšiuose": "Telšiai",
        "telsiai": "Telšiai", "telsiuose": "Telšiai",
        "ukmergė": "Ukmergė", "ukmergėje": "Ukmergė",
        "ukmerge": "Ukmergė", "ukmergeje": "Ukmergė",
        "visaginas": "Visaginas", "visagine": "Visaginas",
        "palanga": "Palanga", "palangoje": "Palanga",
        "plungė": "Plungė", "plungėje": "Plungė",
        "plunge": "Plungė", "plungeje": "Plungė"
    }
    for word, canonical_city in city_canonical_map.items():
        if re.search(r'\b' + re.escape(word) + r'\b', loc):
            return canonical_city

    if re.search(r'\b(?:lietuva|lietuvoje|lithuania|lithuanian)\b', loc):
        return "Lithuania"

    if re.search(r'\b(?:remote|nuotolinis|nuotoliu)\b', loc):
        return "Remote"

    return loc.capitalize()


def extract_experience_rules(text: str) -> Tuple[int, bool]:
    """
    Returns: (min_years_experience, experience_is_mandatory)
    Extracts ONLY factual experience requirements explicitly stated in the text.
    """
    lower = text.lower()
    
    # Explicit 0 years / no experience required
    if any(z in lower for z in ["no experience required", "patirtis nebūtina", "0 years", "0-1 years", "0-1 metų", "pradedantiesiems", "no prior experience"]):
        return (0, False)
        
    # Comprehensive patterns to find stated years of experience
    patterns = [
        r'(\d+)\+?\s*(?:metų|metai|m\.|years?)\s*(?:of\s*)?(?:[a-zA-Z\s\/\,\-]{0,35})?\s*(?:experience|patirtis|patirties)',
        r'(?:experience|patirtis)\s*:\s*(?:at\s+least\s+)?(\d+)\+?\s*(?:years?|metų|metai|m\.)',
        r'(?:at\s+least|minimum|min\.?)\s*(\d+)\+?\s*(?:years?|metų|metai|m\.)\s*(?:of\s*)?(?:[a-zA-Z\s\/\,\-]{0,30})?\s*(?:experience|patirtis)',
        r'turėti\s+(?:ne\s+mažiau\s+kaip\s+)?(\d+)\s*(?:metų|metus|m\.)\s*(?:[a-zA-Z\s\/\,\-]{0,25})?\s*patirt',
        r'ne\s+mažiau\s+kaip\s+(\d+)\s*(?:metų|metai|m\.)\s*(?:[a-zA-Z\s\/\,\-]{0,25})?\s*patirt'
    ]
    for pat in patterns:
        match = re.search(pat, lower)
        if match:
            years = int(match.group(1))
            # Determine if in mandatory or preferred section
            is_mandatory = True
            context_window = lower[max(0, match.start() - 100):min(len(lower), match.end() + 100)]
            if any(p in context_window for p in ["preferred", "plus", "privalumas", "nice to have", "advantage", "naudinga", "is a plus", "galėtų būti privalumas"]):
                is_mandatory = False
            return (years, is_mandatory)
        
    # Junior context with unspecified years
    if "junior" in lower or "jaunesnysis" in lower:
        return (0, False)
        
    return (0, False)


def extract_languages(text: str) -> List[str]:
    lower = text.lower()
    langs = []
    if any(k in lower for k in ["anglų", "english", "en language"]):
        langs.append("English")
    if any(k in lower for k in ["lietuvių", "lithuanian", "lt kalba"]):
        langs.append("Lithuanian")
    if any(k in lower for k in ["vokiečių", "german", "deutsch"]):
        langs.append("German")
    if any(k in lower for k in ["rusų", "russian"]):
        langs.append("Russian")
    return langs


def extract_technical_keywords(text: str) -> List[str]:
    keywords = [
        "Python", "Machine Learning", "AI", "Artificial Intelligence", "Generative AI",
        "LLM", "Deep Learning", "PyTorch", "TensorFlow", "Scikit-Learn", "OpenCV",
        "NLP", "SQL", "Git", "Docker", "FastAPI", "Pandas", "NumPy", "Automation",
        "Agents", "LangChain", "HuggingFace", "RAG", "Data Analysis", "Computer Vision"
    ]
    found = []
    for kw in keywords:
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            found.append(kw)
    return found


def normalize_job(raw: RawJobListing) -> NormalizedJob:
    """Deterministically normalizes a RawJobListing into a standard NormalizedJob."""
    norm_title = normalize_title(raw.title)
    
    # Location and work mode
    work_mode = detect_work_mode(raw.description_raw, raw.location_raw)
    emp_type = detect_employment_type(raw.description_raw, raw.title)
    
    # Education & Experience
    edu_desc, req_degree, degree_mandatory = extract_education_rules(raw.description_raw)
    min_exp, exp_mandatory = extract_experience_rules(raw.description_raw)
    
    # Languages and Tech
    langs = extract_languages(raw.description_raw)
    tech = extract_technical_keywords(f"{raw.title} {raw.description_raw}")
    
    # Clean URLs
    clean_job_url = clean_url(raw.job_url) or raw.job_url
    clean_app_url = clean_url(raw.application_url) if raw.application_url else None
    
    # Clean location
    norm_loc = normalize_location(raw.location_raw)
    norm_comp = normalize_company(raw.company)
    
    # Generate deterministic Job ID
    id_source = f"{norm_comp}|{norm_title}|{norm_loc.lower()}"
    job_id = hashlib.sha256(id_source.encode('utf-8')).hexdigest()[:12]
    
    # Generate initial factual evidence items
    evidence: List[EvidenceItem] = []
    evidence.append(EvidenceItem(
        fact_type=FactType.FACT,
        statement=f"Job title is '{raw.title}' at company '{raw.company}'.",
        source_reference=raw.source
    ))
    evidence.append(EvidenceItem(
        fact_type=FactType.FACT,
        statement=f"Detected work mode: {work_mode.value}, employment type: {emp_type.value}.",
        source_reference=raw.source
    ))
    if edu_desc:
        evidence.append(EvidenceItem(
            fact_type=FactType.FACT,
            statement=f"Education requirement: {edu_desc}.",
            source_reference=raw.source
        ))
    if min_exp > 0:
        evidence.append(EvidenceItem(
            fact_type=FactType.FACT,
            statement=f"Experience requirement: {min_exp} years ({'Mandatory' if exp_mandatory else 'Preferred'}).",
            source_reference=raw.source
        ))
        
    return NormalizedJob(
        job_id=job_id,
        title=raw.title.strip(),
        normalized_title=norm_title,
        company=raw.company.strip(),
        location=norm_loc,
        work_mode=work_mode,
        employment_type=emp_type,
        salary=raw.salary_raw.strip() if raw.salary_raw else None,
        description=raw.description_raw.strip(),
        education_requirements=edu_desc,
        requires_completed_degree=req_degree,
        degree_is_mandatory=degree_mandatory,
        min_years_experience=min_exp,
        experience_is_mandatory=exp_mandatory,
        language_requirements=langs,
        technical_keywords=tech,
        job_url=clean_job_url,
        application_url=clean_app_url,
        source=raw.source,
        discovery_timestamp=raw.discovery_timestamp,
        duplicate_sources=[],
        evidence=evidence
    )
