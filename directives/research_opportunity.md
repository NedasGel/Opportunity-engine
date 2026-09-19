# Directive: Research Opportunity

## 1. Overview & Purpose
This Standard Operating Procedure (SOP) governs the systematic investigation of any market, technology, trend, event, or product. Its objective is to surface validated customer problems, underserved niches, competitive landscapes, viable business opportunities, and falsifiable validation experiments while strictly preventing hallucination and unsubstantiated hype.

---

## 2. Inputs
When orchestrating a research task under this directive, the following inputs are required or optional:

| Input Field | Type | Description | Mandatory? |
|---|---|---|---|
| `opportunity_query` | String | Target topic, market catalyst, product, or trend (e.g., "GTA VI modding and server creator ecosystem"). | Yes |
| `domain_context` | String | Industry vertical, ecosystem dynamics, or specific context boundaries. | No (Recommended) |
| `scope_level` | Enum | `fast_scan` (overview + top opportunities) or `deep_dive` (comprehensive mapping + competitive deep dive + experiment designs). | Yes |
| `target_personas` | Array[String] | Specific target user/customer types (e.g., `["Server Admins", "Mod Creators", "Content Streamers"]`). | No |
| `feasibility_constraints` | Object | Constraints such as solo founder vs team, budget ceiling, time-to-market limits. | No |

---

## 3. Research Objectives
For every targeted opportunity query, the engine must accomplish four core objectives:
1. **Uncover Acute Problems**: Identify painful, recurring friction points where users are already seeking or hacking together workarounds.
2. **Map the Competitive Landscape**: Locate existing direct and indirect solutions, evaluate their weaknesses, and measure market saturation.
3. **Formulate High-Value Business Hypotheses**: Define concrete, monetizable product/service opportunities that solve identified pain points.
4. **Design Rapid Validation Experiments**: Propose lean, measurable tests to validate demand and willingness to pay before writing production code.

---

## 4. Evidence Standards & Source Reliability

### 4.1 Required Evidence Thresholds
- Every claimed market pain point, competitor, or trend must be supported by **at least two independent sources**.
- Market sizing or revenue figures must link directly to verifiable primary data or reputable analyst reports.

### 4.2 Source Reliability Hierarchy

```
+-------------------------------------------------------------+
| TIER 1: HIGH RELIABILITY (Primary Data)                     |
| * Official platform documentation, API specs, SEC filings   |
| * Direct, unprompted user feedback (forums, Reddit, Discord)|
| * Live pricing pages, official terms of service             |
+------------------------------+------------------------------+
                               |
+------------------------------v------------------------------+
| TIER 2: MODERATE RELIABILITY (Secondary Analysis)           |
| * Established trade publications & verified industry reports|
| * Aggregated review platforms (G2, Trustpilot, App Stores)  |
| * Developer repositories with active commit/issue history   |
+------------------------------+------------------------------+
                               |
+------------------------------v------------------------------+
| TIER 3: LOW / SPECULATIVE (Corroboration Required)          |
| * Social media viral claims, anonymous tips, rumors         |
| * Marketing press releases and sponsored promotional posts  |
| * Generic SEO affiliate articles                            |
+-------------------------------------------------------------+
```

> [!IMPORTANT]
> Tier 3 sources may only be used for hypothesis inspiration. No fact or opportunity assessment can be established solely on Tier 3 evidence without Tier 1 or Tier 2 verification.

---

## 5. Distinguishing Facts, Inferences, and Hypotheses
All extracted notes and synthesized findings must be strictly classified into one of three epistemological categories:

1. **`[FACT]` (Empirical Truth)**:
   - A verifiable data point with a specific citation.
   - *Example*: `[FACT]` Take-Two Interactive reported GTA V has sold over 190 million copies as of Q3 2023.
2. **`[INFERENCE]` (Logical Derivation)**:
   - A synthesized conclusion drawn directly from multiple verified facts.
   - *Example*: `[INFERENCE]` Because Rockstar acquired Cfx.re (creators of FiveM), official creator monetization tools will likely be integrated into future franchise releases.
3. **`[HYPOTHESIS]` (Unvalidated Proposition)**:
   - An assumption regarding customer behavior, willingness to pay, or market demand requiring experimentation.
   - *Example*: `[HYPOTHESIS]` FiveM roleplay server owners will pay $29/month for an AI-powered automated voice dispatch moderation bot.

---

## 6. Framework for Identifying Problems
When analyzing data, look for high-conviction problem signals:
- **Active Workarounds**: Users combining multiple disjointed tools (e.g., Google Sheets + Discord webhooks + manual PayPal invoices).
- **Emotional Complaints**: High sentiment friction words in community discussions ("terrible", "nightmare", "waste of hours", "broken", "impossible to configure").
- **Economic Loss / Risk**: Problems causing lost revenue, banned accounts, security breaches, or excessive server downtime.
- **Regulatory / Platform Shifts**: Policy changes or new platform rules that render previous workflows obsolete.

---

## 7. Framework for Identifying Business Opportunities
Evaluate opportunities across standard monetization archetypes:
1. **Picks & Shovels / Developer & Creator Tooling**: SDKs, asset managers, CI/CD, automation scripts, testing frameworks for ecosystem creators.
2. **Workflow Automation & Operations**: Specialized bots, billing automation, customer support agents, CRM/analytics for operators.
3. **Niche Marketplaces & Aggregators**: Matchmaking platforms between service providers, asset buyers, and sellers.
4. **Data Intelligence & Monitoring**: Real-time alerts, competitive intelligence, telemetry, server health tracking.
5. **Audience & Community Infrastructure**: Gated membership software, specialized tournament/event tools, engagement widgets.

---

## 8. Competitor Mapping & Saturation Assessment

### 8.1 Competitor Categorization
- **Direct**: Tools targeting the exact same persona and use case.
- **Indirect**: Broader tools adapted for this use case (e.g., Zapier, Airtable, generic Discord bots).
- **Do-Nothing / In-House**: Open-source scripts or manual labor.

### 8.2 Saturation Signals
| Market Status | Indicators | Action |
|---|---|---|
| **Oversaturated** | Heavy paid ad bidding, commoditized features, aggressive price cuts, high CAC. | Avoid unless 10x differentiation or unfair distribution exists. |
| **Fragmented** | Many small, low-quality tools with poor UI, unmaintained GitHub repos, frequent user churn. | Prime target for polished, reliable, modern alternative. |
| **Emerging / Blue Ocean** | High search growth, active unanswered questions on forums, no dominant commercial player. | High priority target for rapid experiment validation. |

---

## 9. Feasibility & Risk Scoring (1 to 5 Scale)
Each opportunity must receive a feasibility breakdown:

| Dimension | Score 1 (Difficult/Risky) | Score 5 (Ideal/Favorable) |
|---|---|---|
| **Technical Feasibility** | Requires breakthrough research, complex ML, or massive infra. | Can be built as MVP in < 2 weeks with existing APIs/stacks. |
| **Go-To-Market (GTM) Access** | Opaque buyers, gatekeepers, enterprise sales cycles. | Concentrated, highly reachable online communities (Reddit, Discord, X). |
| **Platform / Lock-in Risk** | Dependent on private/undocumented APIs likely to be shut down. | Platform-agnostic or aligned with official platform developer incentives. |
| **Time-to-Value** | Requires months of data onboarding before user sees benefit. | Delivers immediate value upon first setup. |

---

## 10. Experiment Generation Standards
For every promising opportunity, specify 1 to 3 low-cost validation experiments.
Every experiment must include:
- **Experiment Type**: (e.g., Smoke Test Landing Page, Concierge MVP, Pre-sale Offer, Open-Source Lead Magnet, Community Cold Outreach).
- **Core Hypothesis Being Tested**: Explicitly stated in the form: *"If we offer [Value Prop] to [Target Persona], then [X%] will [Take Desired Action] within [Timeframe]."*
- **Execution Steps**: Concrete steps to execute the test without writing unnecessary full-scale software.
- **Quantifiable Success Metric**: Crisp pass/fail criteria (e.g., minimum 15% conversion rate on 100 targeted clicks; 5 pre-order deposits of $20).
- **Kill / Pivot Criteria**: Condition indicating the hypothesis is invalidated.

---

## 11. Standard Output Schema
The orchestrator and execution scripts must generate results adhering to the following structured schema (JSON and Markdown):

```json
{
  "opportunity_query": "string",
  "generated_at": "ISO-8601 Timestamp",
  "scope_level": "fast_scan | deep_dive",
  "market_overview": {
    "summary": "string",
    "key_catalysts": ["string"],
    "evidence_sources": [
      {
        "title": "string",
        "url": "string",
        "reliability_tier": "tier_1 | tier_2 | tier_3",
        "key_facts": ["string"]
      }
    ]
  },
  "identified_problems": [
    {
      "problem_id": "PROB-001",
      "statement": "string",
      "target_persona": "string",
      "severity": "low | medium | high | critical",
      "supporting_evidence": ["string"],
      "status": "FACT | INFERENCE | HYPOTHESIS"
    }
  ],
  "competitor_landscape": [
    {
      "name": "string",
      "type": "direct | indirect | alternative",
      "strengths": ["string"],
      "weaknesses_and_gaps": ["string"],
      "pricing_model": "string"
    }
  ],
  "saturation_level": "undersaturated | fragmented | mature | oversaturated",
  "opportunities": [
    {
      "opportunity_id": "OPP-001",
      "title": "string",
      "archetype": "picks_and_shovels | automation | marketplace | data_intel | community",
      "value_proposition": "string",
      "target_customer": "string",
      "revenue_model": "string",
      "feasibility_scores": {
        "technical": 1,
        "gtm": 1,
        "platform_risk": 1,
        "overall": 1
      },
      "validation_experiments": [
        {
          "experiment_name": "string",
          "type": "smoke_test | concierge_mvp | pre_sale | content_magnet",
          "hypothesis": "string",
          "success_metric": "string",
          "estimated_cost_usd": 0,
          "estimated_duration_days": 7
        }
      ]
    }
  ]
}
```
