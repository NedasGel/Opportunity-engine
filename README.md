# Opportunity Engine

**Opportunity Engine** is an agentic workflow system for turning real-world research problems into structured, evidence-grounded actions.

The project combines **AI-driven reasoning and orchestration** with deterministic execution, validation, and human approval.

The current implementation focuses on **job opportunity discovery and evaluation**: finding relevant positions from multiple sources, normalizing and deduplicating listings, evaluating them against a real candidate profile, and producing an actionable report.

The system is designed around one principle:

> **AI can decide what needs to be done, but deterministic code should handle critical execution and validation wherever possible.**

---

## What It Does

The current job-discovery workflow can:

* search multiple job sources
* collect job listings
* normalize inconsistent listing data
* identify employment type, work mode, education and experience requirements
* preserve evidence from the original listing
* deduplicate the same opportunity across different sources
* evaluate jobs against a specific candidate profile
* detect hard blockers such as mandatory completed degrees or experience requirements
* score opportunities using a structured 100-point model
* generate application-ready recommendations
* draft truthful application messages without inventing candidate experience
* produce Markdown and JSON reports
* preserve direct job and application URLs when they can be reliably identified

The system is **human-in-the-loop**.

It does not automatically apply for jobs.

The final decision remains with the user.

---

## Architecture

The project follows a three-layer architecture:

```text
DIRECTIVES
    ↓
ORCHESTRATION
    ↓
DETERMINISTIC EXECUTION
```

### 1. Directives

Markdown files define the rules, goals and constraints of the system.

```text
directives/
├── candidate_profile.md
├── job_discovery.md
└── research_opportunity.md
```

The candidate profile acts as the source of truth for:

* education
* technical skills
* experience
* career direction
* work preferences
* blockers
* supported claims

This prevents the evaluator from inventing qualifications or experience.

### 2. Orchestration

The orchestration layer controls the overall workflow and determines which execution steps need to happen.

The current implementation uses the job discovery pipeline as the main workflow.

### 3. Deterministic Execution

Python modules perform operations where predictable and testable behavior is important:

```text
execution/
├── models.py
├── normalize.py
├── deduplicate.py
├── evaluate.py
├── report.py
├── pipeline.py
└── sources/
    ├── base.py
    ├── mock_source.py
    ├── cvbankas.py
    ├── cvonline.py
    ├── linkedin.py
    ├── cvmarket.py
    └── work_in_lithuania.py
```

This separation allows the AI-oriented workflow to use deterministic components instead of relying on an LLM for every operation.

---

## Current Workflow

```text
[ DISCOVER ]
      ↓
[ NORMALIZE ]
      ↓
[ DEDUPLICATE ]
      ↓
[ EVALUATE ]
      ↓
[ RANK ]
      ↓
[ REPORT ]
      ↓
[ HUMAN REVIEW ]
```

### Discover

Queries configured job-source adapters and collects available listings.

Current adapters include:

* CVBankas
* CVOnline
* LinkedIn
* CVMarket
* Work in Lithuania
* Mock source for deterministic testing

Sources are implemented behind a common interface so they can be replaced or extended independently.

### Normalize

Different websites represent the same information differently.

The normalization layer converts listings into a common representation and extracts information such as:

* title
* company
* location
* work mode
* employment type
* salary
* description
* technical requirements
* education requirements
* experience requirements
* language requirements
* job URL
* application URL
* evidence

Unknown information remains unknown.

The system does not fill missing information with assumptions.

### Deduplicate

The same position can appear on multiple job boards.

The deduplication layer attempts to identify duplicate opportunities using information such as:

* company
* normalized title
* location
* URLs
* available identifiers

When duplicates are found, useful source information is preserved rather than simply discarded.

### Evaluate

Each opportunity is evaluated against the candidate profile.

The current scoring model has 100 points:

| Dimension                          |  Points |
| ---------------------------------- | ------: |
| Role / domain relevance            |      40 |
| Technical skill overlap            |      15 |
| Experience / student compatibility |      20 |
| Schedule compatibility             |      10 |
| Location / work mode               |      10 |
| Language compatibility             |       5 |
| **Total**                          | **100** |

The largest part of the score therefore comes from **actual technical and domain relevance**, rather than simply being a student or being located in Vilnius.

The evaluator prioritizes:

1. AI / ML
2. Generative AI / LLMs
3. AI agents / agentic systems
4. AI automation
5. Applied AI
6. NLP
7. AI-related data science
8. Python automation and data-oriented technical work
9. Other technically relevant software roles

Generic software and non-technical positions are treated as lower relevance.

Importantly, relevance is not determined solely by job title.

For example:

```text
Python Automation Intern
```

can be highly relevant even if the description never explicitly says "AI".

Likewise:

```text
AI Engineer
```

does not automatically guarantee a high score if the actual responsibilities do not match the candidate's direction.

### Hard blockers

The evaluator can identify requirements that make an opportunity unsuitable regardless of its other characteristics.

Examples include:

* mandatory completed degree
* mandatory multi-year professional experience
* mandatory incompatible language
* incompatible location without a viable remote option

Preferred or "nice to have" requirements are not automatically treated as blockers.

### Evidence grounding

The system distinguishes between:

```text
[FACT]
[INFERENCE]
[RECOMMENDATION]
```

For example:

```text
[FACT]
The listing states that students may apply.

[FACT]
The position is hybrid in Vilnius.

[INFERENCE]
The opportunity appears compatible with the candidate's current studies.

[RECOMMENDATION]
Worth reviewing / applying.
```

The system should never turn an inference into a claimed fact.

---

## Recommendation Tiers

The evaluator currently produces four recommendation levels:

```text
APPLY
CONSIDER
LOW_PRIORITY
REJECT
```

`APPLY` is not automatic application.

It means the opportunity passed the engine's relevance and compatibility criteria and should be reviewed by the candidate before applying.

The human remains responsible for the final decision.

---

## Candidate Grounding

The current candidate profile represents a real second-year Artificial Intelligence student at VILNIUS TECH.

Relevant technical background includes:

* Python
* C
* C++
* AI fundamentals
* ML fundamentals
* LLM / GenAI fundamentals
* AI agents
* AI automation
* OOP
* recursion
* data structures
* algorithms
* Git / GitHub
* Linux / WSL
* MATLAB

The system explicitly avoids claiming professional AI/ML experience that the candidate does not have.

---

## Personal Project

The current implementation is itself built around a real problem: finding relevant job opportunities while avoiding the large amount of irrelevant results produced by generic job searches.

The project is not treated as professional employment experience.

It demonstrates work with:

* agentic workflows
* structured directives
* Python execution
* data normalization
* multi-source ingestion
* deduplication
* rule-based validation
* scoring systems
* evidence grounding
* automated reporting
* human approval workflows

---

## Project Structure

```text
opportunity-engine/
│
├── directives/
│   ├── candidate_profile.md
│   ├── job_discovery.md
│   └── research_opportunity.md
│
├── execution/
│   ├── models.py
│   ├── normalize.py
│   ├── deduplicate.py
│   ├── evaluate.py
│   ├── report.py
│   ├── pipeline.py
│   │
│   └── sources/
│       ├── base.py
│       ├── mock_source.py
│       ├── cvbankas.py
│       ├── cvonline.py
│       ├── linkedin.py
│       ├── cvmarket.py
│       └── work_in_lithuania.py
│
├── tests/
│   ├── test_normalization.py
│   ├── test_evaluation.py
│   ├── test_deduplication.py
│   ├── test_urls_and_safety.py
│   ├── test_candidate_grounding.py
│   ├── test_pipeline.py
│   └── test_multi_sources.py
│
├── .env.example
├── .gitignore
└── README.md
```

---

## Testing

The project includes unit and integration tests covering:

* normalization
* evaluation and scoring
* hard blockers
* deduplication
* URL safety
* candidate-profile grounding
* application-message generation
* multi-source behavior
* end-to-end pipeline execution

Current test status:

```text
33 passed
0 failed
```

Tests use deterministic fixtures where possible so core behavior can be validated without relying entirely on live websites.

---

## Running the Project

### Install / setup

The project currently uses Python's standard tooling and does not require a large external framework for the core execution pipeline.

### Run tests

```bash
py -m unittest discover -s tests
```

### Run the discovery pipeline

```bash
py -m execution.pipeline
```

### Run with a specific source

```bash
py -m execution.pipeline --source mock
```

### Run with a custom query

```bash
py -m execution.pipeline --query "Python intern" --output .tmp/
```

Generated reports and temporary execution artifacts are written to `.tmp/`.

---

## Safety and Reliability Principles

The project is intentionally conservative about information it does not know.

It does not intentionally:

* invent candidate experience
* invent job requirements
* invent salaries
* fabricate application URLs
* treat preferences as mandatory requirements
* bypass authentication or access controls
* automatically submit applications

When information is unavailable, the system should represent it as unknown rather than guessing.

---

## Current Scope

The current implementation is focused on **job opportunity discovery and evaluation**.

The underlying architecture is designed to support additional evidence-grounded workflows in the future without turning every operation into an LLM-generated action.

Potential future directions include:

* evaluating a job URL supplied directly by a user
* additional legitimate job sources
* richer opportunity research
* persistent opportunity state
* application tracking
* human approval workflows
* additional research-oriented directives

These are future directions, not claims about functionality already implemented.

---

## Why This Project Exists

Traditional job search often produces a large number of technically irrelevant opportunities.

Opportunity Engine is an attempt to solve that problem as an engineering system:

```text
Real-world problem
       ↓
AI-assisted reasoning
       ↓
Structured workflow
       ↓
Deterministic execution
       ↓
Validation
       ↓
Evidence
       ↓
Human decision
```

The goal is not to replace the human decision.

The goal is to make the work leading to that decision more reliable, repeatable and useful.
