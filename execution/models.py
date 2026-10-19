from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any


class WorkMode(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class EmploymentType(str, Enum):
    INTERNSHIP = "internship"
    PART_TIME = "part_time"
    WORKING_STUDENT = "working_student"
    ENTRY_LEVEL = "entry_level"
    FULL_TIME = "full_time"
    CONTRACT = "contract"
    UNKNOWN = "unknown"


class Recommendation(str, Enum):
    APPLY = "APPLY"
    CONSIDER = "CONSIDER"
    LOW_PRIORITY = "LOW_PRIORITY"
    REJECT = "REJECT"


class FactType(str, Enum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    RECOMMENDATION = "RECOMMENDATION"


@dataclass
class EvidenceItem:
    fact_type: FactType
    statement: str
    source_reference: Optional[str] = None

    def format(self) -> str:
        ref_part = f" (Source: {self.source_reference})" if self.source_reference else ""
        return f"[{self.fact_type.value}] {self.statement}{ref_part}"


@dataclass
class CandidateProfile:
    current_education: str = "2nd-year undergraduate student in Artificial Intelligence"
    location: str = "Vilnius, Lithuania"
    spoken_languages: List[str] = field(default_factory=lambda: ["Lithuanian", "English"])
    target_interests: List[str] = field(default_factory=lambda: [
        "AI", "Machine Learning", "Generative AI", "AI agents", "AI automation", "Automation", "Python"
    ])
    professional_technical_experience_years: int = 0
    non_technical_experience: List[str] = field(default_factory=lambda: ["Barbora courier", "Bolt courier"])
    willing_to_apply_incomplete_match: bool = True
    completed_degree: bool = False
    preferred_employment_types: List[str] = field(default_factory=lambda: [
        "part_time", "internship", "working_student", "entry_level"
    ])


@dataclass
class RawJobListing:
    raw_id: str
    title: str
    company: str
    location_raw: str
    description_raw: str
    job_url: str
    salary_raw: Optional[str] = None
    application_url: Optional[str] = None
    source: str = "unknown"
    discovery_timestamp: str = ""
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedJob:
    job_id: str
    title: str
    normalized_title: str
    company: str
    location: str
    work_mode: WorkMode
    employment_type: EmploymentType
    salary: Optional[str]
    description: str
    required_qualifications: List[str] = field(default_factory=list)
    preferred_qualifications: List[str] = field(default_factory=list)
    education_requirements: Optional[str] = None
    requires_completed_degree: bool = False
    degree_is_mandatory: bool = False
    min_years_experience: int = 0
    experience_is_mandatory: bool = False
    # Populated by execution.agentic_extractor (None = not extracted / unstated)
    required_experience_years: Optional[int] = None
    is_strictly_full_time: Optional[bool] = None
    extraction_method: str = "regex"
    language_requirements: List[str] = field(default_factory=list)
    technical_keywords: List[str] = field(default_factory=list)
    posted_date: Optional[str] = None
    closing_date: Optional[str] = None
    job_url: str = ""
    application_url: Optional[str] = None
    source: str = "unknown"
    discovery_timestamp: str = ""
    duplicate_sources: List[Dict[str, str]] = field(default_factory=list)
    evidence: List[EvidenceItem] = field(default_factory=list)


@dataclass
class ScoreBreakdown:
    ai_relevance: float
    student_compatibility: float
    location_compatibility: float
    schedule_compatibility: float
    education_compatibility: float
    technical_skill_overlap: float
    language_compatibility: float
    total_score: float


@dataclass
class EvaluationResult:
    job_id: str
    normalized_job: NormalizedJob
    score_breakdown: ScoreBreakdown
    total_score: float
    recommendation: Recommendation
    hard_blockers: List[str] = field(default_factory=list)
    soft_penalties: List[str] = field(default_factory=list)
    strong_matches: List[str] = field(default_factory=list)
    weak_matches: List[str] = field(default_factory=list)
    missing_information: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    application_message_draft: Optional[str] = None


# ---------------------------------------------------------------------------
# Serialization helpers (used by the SQLite state store for result caching).
# Round-trip is lossless: evaluation_from_dict(evaluation_to_dict(r)) == r
# ---------------------------------------------------------------------------

def _enum_safe(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _enum_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_enum_safe(v) for v in obj]
    return obj


def evaluation_to_dict(result: EvaluationResult) -> Dict[str, Any]:
    return _enum_safe(asdict(result))


def _evidence_from_dict(d: Dict[str, Any]) -> EvidenceItem:
    return EvidenceItem(
        fact_type=FactType(d["fact_type"]),
        statement=d["statement"],
        source_reference=d.get("source_reference"),
    )


def normalized_job_from_dict(d: Dict[str, Any]) -> NormalizedJob:
    data = dict(d)
    data["work_mode"] = WorkMode(data["work_mode"])
    data["employment_type"] = EmploymentType(data["employment_type"])
    data["evidence"] = [_evidence_from_dict(e) for e in data.get("evidence", [])]
    return NormalizedJob(**data)


def evaluation_from_dict(d: Dict[str, Any]) -> EvaluationResult:
    data = dict(d)
    data["normalized_job"] = normalized_job_from_dict(data["normalized_job"])
    data["score_breakdown"] = ScoreBreakdown(**data["score_breakdown"])
    data["recommendation"] = Recommendation(data["recommendation"])
    data["evidence_items"] = [_evidence_from_dict(e) for e in data.get("evidence_items", [])]
    return EvaluationResult(**data)
