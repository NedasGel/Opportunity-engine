# Directive: Personal Job Discovery Workflow

## 1. Overview & Purpose
This Standard Operating Procedure (SOP) defines the automated discovery, normalization, deduplication, evaluation, ranking, and reporting pipeline for personal job opportunities tailored to a 2nd-year AI student based in Vilnius, Lithuania.

The goal is to provide evidence-grounded, explainable, and application-ready job recommendations without ever performing automated submissions. Human approval remains the final required step.

---

## 2. Workflow Pipeline
The discovery workflow strictly follows the six-stage deterministic pipeline:

```
[ DISCOVER ] ──► [ NORMALIZE ] ──► [ DEDUPLICATE ] ──► [ EVALUATE ] ──► [ RANK ] ──► [ REPORT ]
```

1. **DISCOVER**: Ingest raw job listings from modular sources (e.g., CVBankas, public job feeds, career pages, mock test fixtures).
2. **NORMALIZE**: Parse raw listings into the standard `NormalizedJob` schema, standardizing work mode, employment type, salary, requirements, and validating URLs.
3. **DEDUPLICATE**: Group duplicate postings across sources by company, normalized title, location, and canonical URLs, preserving all source metadata.
4. **EVALUATE**: Score job suitability on a transparent 100-point rubric, identifying hard blockers, soft penalties, strong/weak matches, missing info, and concerns.
5. **RANK**: Sort deduplicated jobs by total suitability score and recommendation tier (`APPLY` > `CONSIDER` > `LOW_PRIORITY` > `REJECT`).
6. **REPORT**: Format results into structured Markdown and JSON reports adhering to evidence standards (`[FACT]`, `[INFERENCE]`, `[RECOMMENDATION]`).

---

## 3. Evaluation & Scoring Model (100 Points Total)

Each job receives an explainable score based on seven weighted factors:

| Factor | Max Points | Evaluation Criteria |
|---|---|---|
| **1. AI/ML/Automation Relevance** | 25 | Direct AI/ML/Agents/Automation focus (20-25); Software/Python/Data role with AI relevance (12-19); General software role (6-11); Unrelated (0-5). |
| **2. Student / Experience Compatibility** | 20 | Explicitly student-friendly or no prior experience required (18-20); Junior with 0-1 yr preferred (12-17); Junior with 1-2 yrs preferred (5-11); 2+ yrs mandatory (0 + Hard Blocker). |
| **3. Work Arrangement & Location** | 15 | Remote (Lithuania/EU) or Hybrid in Vilnius (14-15); On-site in Vilnius (11-13); Other accessible LT location (6-10); Incompatible location (0 + Hard Blocker). |
| **4. Employment Type & Schedule** | 15 | Part-time, flexible student hours, working student, paid internship (13-15); Full-time internship with student compatibility (9-12); Standard entry-level full-time (4-8); Unpaid/volunteer (0). |
| **5. Education Compatibility** | 10 | Current university students welcome (9-10); Degree not specified / general field without completion mandate (6-8); Strict mandatory completed degree (0 + Hard Blocker). |
| **6. Technical Skill Overlap (Known Info Only)** | 10 | Core AI/Python/Data foundations aligned with 2nd-year AI study (8-10); General software engineering concepts (5-7); Heavy senior legacy stack (1-4). |
| **7. Language Compatibility** | 5 | Lithuanian and/or English accepted (5); Incompatible mandatory language (0 + Hard Blocker). |

---

## 4. Hard Blockers vs. Soft Penalties

- **Hard Blockers**: Disqualify the job or set recommendation to `REJECT`:
  - Mandatory completed Bachelor's or Master's degree.
  - Mandatory requirement for multiple years (2+) of professional experience.
  - Mandatory language the candidate does not speak (e.g., German-only).
  - Ineligible geographic location without remote option.
- **Soft Penalties**: Reduce score but do NOT trigger automatic rejection:
  - "1 year of experience preferred / nice to have".
  - Specific framework / tool preferred.
  - Previous internship experience preferred.
  - Full-time position with unknown flexibility.

---

## 5. Evidence Tagging Rules
Every extracted claim and assessment in reports must be explicitly tagged:
- `[FACT]`: Direct empirical statement from the job listing or candidate profile.
- `[INFERENCE]`: Analytical deduction combining facts.
- `[RECOMMENDATION]`: Actionable advice for the candidate.

---

## 6. URL Handling & Safety Constraints
- `job_url`: Must be a verified direct link to the opportunity listing.
- `application_url`: Must be the verified direct URL to start the application (e.g. ATS link, email mailto, or application form). Set to `null` if not identifiable.
- **NEVER fabricate URLs, guess URL patterns, or convert third-party aggregators into fake direct links.**
