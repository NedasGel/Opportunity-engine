"""
Deterministic pre-filter that drops obviously non-technical job listings
(manual labour, retail, transport, hospitality, care, trades) BEFORE evaluation.

Design principle: DEFAULT-PASS.
A job is rejected only on positive evidence that it is non-technical, and never
when its title carries any technical signal. Anything ambiguous is passed through
to the full evaluator, which is far better equipped to score it.

The rule set is intentionally NARROWER than evaluate.NON_TECH_STRICT_PATTERNS:
stems such as 'administratori', 'vadybinink', 'operatori', 'finans', 'logistik'
are deliberately NOT blocked because they occur in legitimate IT titles
(e.g. 'Sistemų administratorius', 'IT projektų vadybininkas').

Bump PREFILTER_VERSION whenever the rules change; the state store will then
re-run the pre-filter over previously rejected listings.
"""
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Pattern

from .models import NormalizedJob

PREFILTER_VERSION = "1"


def fold(text: str) -> str:
    """Lowercase and strip diacritics so 'Pardavėjas' and 'Pardavejas' match identically."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# ---------------------------------------------------------------------------
# Title allowlist: ANY match means the job is never pre-filtered.
# Patterns operate on folded (ASCII, lowercase) text.
# ---------------------------------------------------------------------------
TECH_ALLOW_PATTERNS: List[str] = [
    r'\b(?:it|ai|di|ml|llm|nlp|qa|bi|erp|crm|sap|gis|plc|rpa|soc)\b',
    r'\bdata\b', r'\bduomen', r'\bpython', r'\bjava', r'\bsql\b',
    r'\bprogramuotoj', r'\bdeveloper', r'\bengineer', r'\binzinier',
    r'\bsoftware', r'\bprogram', r'\bsistem', r'\bsystem', r'\btinkl', r'\bnetwork',
    r'\banaly', r'\banalitik', r'\bautomat', r'\brobot', r'\btech', r'\btechnolog',
    r'\bcloud', r'\bdebesij', r'\bdevops', r'\btest', r'\bcyber', r'\bkibernet',
    r'\bsecurity', r'\bmachine\s+learning', r'\bdirbtin', r'\bdigital', r'\bskaitmenin',
    r'\bpraktik', r'\bintern', r'\btrainee', r'\bstazuot',
]

# ---------------------------------------------------------------------------
# Title blocklist: manual labour / retail / transport / hospitality / care / trades.
# ---------------------------------------------------------------------------
BLOCK_PATTERNS: List[str] = [
    # Lithuanian stems (diacritics folded)
    r'\bdarbinink', r'\bpardavej', r'\bekspeditori', r'\bvairuotoj', r'\bkasinink',
    r'\bvirej', r'\bpadavej', r'\bbarmen', r'\bvalytoj', r'\bkambarin',
    r'\bsandelinink', r'\bkrovej', r'\bkomplektuotoj', r'\bpakuotoj', r'\bisdestytoj',
    r'\bmontuotoj', r'\bspaudej', r'\bparduotuv',
    r'\bsuvirintoj', r'\bsantechnik', r'\bmurinink', r'\bdazytoj', r'\bstaliu',
    r'\bstatybinink', r'\bapdailinink', r'\bstogdeng', r'\bbetonuotoj',
    r'\belektrik(?:as|e|ai|u)\b', r'\bmechanik(?:as|e|ai|u)\b', r'\bsaltkalv',
    r'\bslaug', r'\baukl(?:e|es|iu)\b', r'\bkirpej', r'\bkosmetolog',
    r'\bmasazuotoj', r'\bapsaugos\s+darbuotoj', r'\bsargas\b', r'\bsiuvej',
    r'\bkepej', r'\bkonditer', r'\bmesinink', r'\bkurjer', r'\brestoran',
    r'\bpsicholog', r'\bterapij', r'\bterapeut', r'\bsocialin\w*\s*(?:\(-\w+\)\s*)?darbuotoj',
    r'\bteisinink',
    r'\b(?:gamybos|linijos|cnc)\s+operatori', r'\bstaklinink',
    # English
    r'\b(?:warehouse|construction|factory|production)\s+(?:worker|operative|associate)',
    r'\b(?:driver|courier|cashier|cleaner|housekeeper|waiter|waitress|barista|cook|chef)s?\b',
    r'\b(?:welder|plumber|electrician|carpenter|picker|packer|forklift)s?\b',
    r'\b(?:sales\s+(?:assistant|associate|consultant)|shop\s+assistant)\b',
]

# ---------------------------------------------------------------------------
# Description override: a blocked title is still PASSED if the description
# contains at least MIN_TECH_SIGNALS distinct strong technical signals.
# ---------------------------------------------------------------------------
STRONG_TECH_PATTERNS: List[str] = [
    r'\bpython\b', r'\bsql\b', r'\bmachine\s+learning\b', r'\bdeep\s+learning\b',
    r'\bpytorch\b', r'\btensorflow\b', r'\bllms?\b', r'\bapi\b', r'\bgit\b',
    r'\bdocker\b', r'\bkubernetes\b', r'\bprogramavim', r'\balgoritm',
    r'\bdata\s+pipeline',
]
MIN_TECH_SIGNALS = 2

_ALLOW: List[Pattern[str]] = [re.compile(p) for p in TECH_ALLOW_PATTERNS]
_BLOCK: List[Pattern[str]] = [re.compile(p) for p in BLOCK_PATTERNS]
_STRONG: List[Pattern[str]] = [re.compile(p) for p in STRONG_TECH_PATTERNS]


@dataclass(frozen=True)
class PrefilterDecision:
    passed: bool
    reason: str
    matched_pattern: Optional[str] = None


@dataclass(frozen=True)
class PrefilteredJob:
    """A job dropped by the pre-filter (this run or a previous run), for audit reporting."""
    job: NormalizedJob
    reason: str
    from_cache: bool = False


def _first_match(patterns: List[Pattern[str]], text: str) -> Optional[str]:
    for pat in patterns:
        if pat.search(text):
            return pat.pattern
    return None


def prefilter_title(title: str, description: str = "") -> PrefilterDecision:
    """Core decision function operating on raw strings (convenient for tests)."""
    title_f = fold(title)

    allow_hit = _first_match(_ALLOW, title_f)
    if allow_hit:
        return PrefilterDecision(True, "tech_allowlist", allow_hit)

    block_hit = _first_match(_BLOCK, title_f)
    if not block_hit:
        return PrefilterDecision(True, "default_pass")

    desc_f = fold(description)
    signals = sum(1 for pat in _STRONG if pat.search(desc_f))
    if signals >= MIN_TECH_SIGNALS:
        return PrefilterDecision(True, f"description_override ({signals} tech signals)", block_hit)

    return PrefilterDecision(False, f"non_tech_title: {block_hit}", block_hit)


def prefilter_job(job: NormalizedJob) -> PrefilterDecision:
    """Pre-filter a normalized job. Returns a decision; never raises."""
    return prefilter_title(job.title, job.description)
