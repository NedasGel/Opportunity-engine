# AI Opportunity Discovery Engine

A general-purpose, autonomous research and analysis system designed to investigate markets, events, technologies, products, and trends to systematically discover profitable problems, underserved customer segments, commercial opportunities, and actionable validation experiments.

---

## Purpose & Scope

The goal of this engine is **not** to build a single static business idea. Instead, it is a modular, domain-agnostic discovery engine capable of ingesting any market topic or catalyst—from major entertainment releases to enterprise software shifts—and surfacing grounded, evidence-backed business hypotheses and experiments.

While our first validation target will be the launch ecosystem surrounding **Grand Theft Auto VI (GTA VI)**, the entire architecture is strictly decoupled from any single domain to ensure complete reusability across any future market or opportunity.

---

## System Architecture

The engine operates on a layered model ensuring separation of concerns between operational standards, cognitive planning, and deterministic execution.

`
+-------------------------------------------------------------+
|                       1. DIRECTIVES                         |
|   (Markdown SOPs: criteria, schemas, evaluation guidelines) |
+------------------------------+------------------------------+
                               | reads & adheres to
+------------------------------v------------------------------+
|                      2. ORCHESTRATION                       |
|    (AI Agent: workflow planning, tool dispatch, evaluation) |
+------------------------------+------------------------------+
                               | invokes deterministically
+------------------------------v------------------------------+
|                        3. EXECUTION                         |
|    (Python Scripts: API calls, parsing, data pipelines, DB) |
+-------------------------------------------------------------+
`

### 1. Directives (directives/)
Markdown Standard Operating Procedures (SOPs) that specify *how* the engine investigates, evaluates, and structures tasks. Directives define research objectives, evidence standards, source reliability tiers, scoring rubrics, and output schemas.

### 2. Orchestration
The AI reasoning layer responsible for:
- Reading and strictly adhering to applicable directives.
- Determining sub-tasks, sequencing, and tool invocations.
- Evaluating execution script outputs against validation rules.
- Handling unexpected tool errors and replanning.
- Synthesizing findings into structured outputs.

### 3. Execution (execution/)
Deterministic Python scripts handling concrete operations:
- Data collection and API integrations (e.g., search, web scraping, data enrichment).
- Deterministic data processing, normalization, and hashing.
- File system and database read/write operations.
- Repeatable, idempotent tasks that should not rely on probabilistic LLM logic.

---

## Supporting Layers

In addition to the core 3-layer execution model, the system incorporates four foundational reliability layers:

| Layer | Responsibility |
|---|---|
| **4. State / Database** | Maintains persistent records of discovered sources, extracted entities, generated hypotheses, evaluated opportunities, and validation experiments to prevent redundant work. |
| **5. Validation (	ests/)** | Enforces data integrity checks, source verification, schema conformance, and automated unit tests to prevent hallucinations, malformed outputs, and workflow breaks. |
| **6. Logging / Monitoring** | Emits structured, traceable logs for every significant operation (API queries, cost tracking, token usage, state mutations) for auditability and debugging. |
| **7. Human Approval** | Enforces a safety gating mechanism where consequential actions (e.g., paid API usage, public outreach, external communications, or deployments) require explicit human review. |

---

## Development Philosophy

- **Deterministic over Probabilistic**: If a task can be solved deterministically with Python (e.g., JSON validation, deduplication, regex parsing, mathematical scoring), keep it in deterministic code rather than in prompt text.
- **Incremental & Modular**: Build components strictly on demand. No premature abstractions, fake APIs, or dummy credentials.
- **Evidence-Driven**: Every insight or hypothesis must be anchored to verifiable primary or secondary sources with transparent source reliability ratings.
- **Secure by Design**: Credentials and secrets are managed via .env (never committed). Intermediate and scratch data remain in .tmp/.

---

## Repository Structure

`
opportunity-engine/
|-- directives/                # Markdown SOPs defining workflows & evaluation rubrics
|   -- research_opportunity.md # SOP for investigating target opportunities
|-- execution/                 # Deterministic Python scripts (APIs, scrapers, processors)
|   -- .gitkeep
|-- tests/                     # Unit tests, schema checks, and validation suites
|   -- .gitkeep
|-- .tmp/                      # Ignored directory for intermediate data & cache
|   -- .gitkeep
|-- .env.example               # Template for required environment variables
|-- .gitignore                 # Version control exclusions
-- README.md                  # Project overview & architectural guide
`
