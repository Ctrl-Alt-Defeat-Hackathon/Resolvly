# Resolvly — Insurance Claim & Billing Debugger
## Comprehensive Project Overview

> An AI-powered platform that decodes insurance denials, fetches live federal regulations, and generates ready-to-send appeal letters in under 20 seconds.

---

## Table of Contents

1. [Application Identity](#1-application-identity)
2. [Tech Stack](#2-tech-stack)
3. [System Architecture](#3-system-architecture)
4. [Full Pipeline Workflow](#4-full-pipeline-workflow)
5. [Module Deep-Dives](#5-module-deep-dives)
6. [API Reference](#6-api-reference)
7. [Data Model — ClaimObject](#7-data-model--claimobject)
8. [External Data Sources](#8-external-data-sources)
9. [LLM Client & Fallback Chain](#9-llm-client--fallback-chain)
10. [Features](#10-features)
11. [Configuration & Deployment](#11-configuration--deployment)

---

## 1. Application Identity

**Name:** Resolvly
**Purpose:** Help patients navigate insurance claim denials by automatically extracting claim data from uploaded documents, fetching live regulations, classifying the denial root cause, calculating deadlines, and generating formal appeal letters — all deterministically where possible, with LLM augmentation for narrative and contextual content.

**Problem:** Insurance denial letters contain opaque codes (e.g., `CO-197`), legal citations, and deadlines that most patients cannot interpret. Without knowing what those codes mean, which laws apply to their specific plan, and what steps to take within which deadlines, most patients give up — leaving billions in legitimate claims unpaid.

**Solution:** A patient uploads their denial letter, EOB (Explanation of Benefits), and medical bill. The system runs a multi-agent analysis pipeline and produces a complete action plan: plain-English summary, prioritized action steps, a ready-to-send appeal letter, provider and insurer messages, and a regulatory routing card — in ~15 seconds.

---

## 2. Tech Stack

### Backend
| Component | Technology |
|---|---|
| Framework | FastAPI (Python 3.12+) |
| Server | Uvicorn (ASGI) |
| Data validation | Pydantic v2 |
| PDF extraction | pdfplumber (primary), PyMuPDF / fitz (fallback) |
| OCR (server-side) | pytesseract + Pillow (optional, returns 501 if absent) |
| LLM API | OpenAI-compatible (gpt-4o-mini primary, gpt-4o fallback) |
| Local LLM fallback | Ollama (configurable, development only) |
| PDF export | fpdf2 |
| HTTP client | httpx (async) |
| Rate limiting | slowapi |
| Concurrency | asyncio, asyncio.Semaphore, asyncio.PriorityQueue |
| Code cache | SQLite (via `code_cache.py`) |

### Frontend
| Component | Technology |
|---|---|
| Framework | Vite + React |
| Deployment | Vercel |

### Infrastructure
| Component | Technology |
|---|---|
| Containerization | Docker + docker-compose |
| Backend hosting | Render (Docker runtime) |
| CORS | Configured for localhost:3000/5173 and `*.vercel.app` |

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT (Browser / Frontend)                     │
│                                                                               │
│   Upload documents → Answer wizard questions → Begin Forensic Analysis       │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │ HTTPS
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Application (main.py)                        │
│                                                                               │
│  Rate Limiter (slowapi)  │  CORS Middleware  │  Swagger /docs  │  /health    │
│                                                                               │
│ ┌─────────────────────────────────────────────────────────────────────────┐  │
│ │                           API ROUTES                                    │  │
│ │                                                                         │  │
│ │  POST /documents/upload          →  upload.py                          │  │
│ │  POST /documents/extract         →  extract.py                         │  │
│ │  POST /documents/ocr/page        →  ocr.py                             │  │
│ │  POST /wizard/plan-type          →  wizard.py                          │  │
│ │  POST /claims/analyze            →  analyze.py (sync)                  │  │
│ │  POST /claims/analyze/stream     →  analyze.py (SSE streaming)         │  │
│ │  POST /outputs/summary           →  outputs.py                         │  │
│ │  POST /outputs/action-checklist  →  outputs.py                         │  │
│ │  POST /outputs/appeal-letter     →  outputs.py                         │  │
│ │  POST /outputs/provider-brief    →  outputs.py                         │  │
│ │  POST /outputs/deadlines         →  outputs.py                         │  │
│ │  POST /outputs/completeness      →  outputs.py                         │  │
│ │  POST /outputs/routing-card      →  outputs.py                         │  │
│ │  POST /outputs/assumptions       →  outputs.py                         │  │
│ │  POST /outputs/probability       →  outputs.py                         │  │
│ │  POST /export/pdf                →  export.py                          │  │
│ │  POST /export/ics                →  export.py                          │  │
│ │  GET  /codes/lookup              →  codes.py                           │  │
│ │  GET  /health                    →  health.py                          │  │
│ └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│ ┌───────────────────┐  ┌───────────────────┐  ┌────────────────────────────┐ │
│ │ EXTRACTION LAYER  │  │   AGENT LAYER     │  │      ANALYSIS LAYER        │ │
│ │                   │  │                   │  │                            │ │
│ │ pdf_extractor     │  │ orchestrator      │  │ root_cause_classifier      │ │
│ │ regex_extractor   │  │ code_lookup_agent │  │ completeness_checker       │ │
│ │ llm_extractor     │  │ regulation_agent  │  │ deadline_calculator        │ │
│ │ document_stitcher │  │ state_rules_agent │  │ probability_estimator      │ │
│ │ confidence_scorer │  │ analysis_agent    │  │ severity_triage            │ │
│ │ schema (models)   │  │ output_agent      │  │ financial_reconciliation   │ │
│ └───────────────────┘  └───────────────────┘  │ validation_loop            │ │
│                                                └────────────────────────────┘ │
│                                                                               │
│ ┌─────────────────────────────────────────────────────────────────────────┐  │
│ │                           TOOLS LAYER                                   │  │
│ │                                                                         │  │
│ │  llm_client       carc_rarc_lookup   cms_icd_lookup    cms_hcpcs_lookup │  │
│ │  npi_registry     ecfr_search        erisa_search      aca_search       │  │
│ │  idoi_search      cms_coverage       state_doi_lookup  code_cache       │  │
│ │  regulatory_fetch web_search                                            │  │
│ └─────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴──────────────┐
                    ▼                            ▼
          External APIs                   Local Data
          ─────────────                   ──────────
          CMS ICD-10 API                  CARC/RARC table
          CMS HCPCS API                   state_doi_contacts.json
          NPPES NPI Registry              state_appeal_rules.json
          eCFR.gov API                    SQLite code cache
          DOL ERISA reference
          Google Custom Search (fallback)
          OpenAI API / Ollama
```

---

## 4. Full Pipeline Workflow

The user journey and system pipeline in order:

```
USER ACTIONS
    │
    ▼
[1] DOCUMENT UPLOAD
    POST /api/v1/documents/upload
    │
    ├── Accepts up to 5 files (PDF, JPG, PNG, WEBP, TIFF), max 10 MB each
    ├── Generates upload_id (UUID) to track the session
    ├── For each file: calls extract_document()
    │     ├── Digital PDF   → pdfplumber (primary) → PyMuPDF (fallback)
    │     ├── Per-page OCR detection:
    │     │     text_chars < 30 AND has_images → is_scanned = True
    │     ├── Mixed documents: pdf_mixed type with scanned_page_numbers list
    │     └── Images / scanned → needs_client_ocr = True (Tesseract.js on frontend)
    │         or POST /ocr/page for server-side pytesseract fallback
    │
    ▼
[2] WIZARD (optional but recommended)
    POST /api/v1/wizard/plan-type
    │
    ├── User answers: plan source (employer/marketplace/Medicaid/individual)
    │                 employer plan type (ERISA/fully insured/unknown)
    │                 employer size (under_50 / 50–999 / 1000+)
    │                 state (2-letter code)
    ├── Bayesian logic: employer size 1000+ → assume ERISA (~80% of large employers)
    ├── ERISA citation override: if denial letter cites ERISA §503 → force ERISA
    ├── Returns: regulation_type, appeal_path, primary_regulator,
    │           applicable_laws (fetched live from eCFR), state DOI contact
    └── Sets regulation_type_source = "user" | "extracted" | "defaulted"
    │
    ▼
[3] ENTITY EXTRACTION
    POST /api/v1/documents/extract
    │
    ├── Multi-document stitching (document_stitcher.py):
    │     ├── Classify each document using weighted feature-scoring (not keyword count)
    │     │     Score = sum of matched regex rule weights (2–5 pts each)
    │     │     confidence = (winner − runner_up) / winner
    │     │     confidence < 0.30 → classified as "requires_review"
    │     ├── Quality-rank duplicates (deny letter with CARC codes wins over vague one)
    │     ├── Claim-ID consistency check (warn on conflicting reference numbers)
    │     └── Field authority rules (merge into one ClaimObject):
    │           denial letter  → claim ID, denial date, appeal deadlines
    │           EOB            → CARC/RARC codes, financial amounts, procedure codes
    │           hospital bill  → facility name, itemized charges
    │
    ├── Pass 1 — Regex Extractor (extract_pass1):
    │     ├── Dates: date_of_denial, date_of_service, date_of_eob
    │     ├── IDs: claim_reference_number, member_id, NPI (Luhn-validated), policy/group number
    │     ├── CARC codes with group prefix (CO-, PR-, OA-, PI-, CR-)
    │     ├── RARC codes
    │     ├── ICD-10, CPT, HCPCS, modifier codes
    │     ├── Financial amounts via labeled patterns:
    │     │     "Billed Amount: $1,234.56" (labeled, conf=0.88)
    │     │     positional currency fallback (conf=0.50)
    │     └── Prior auth status
    │
    ├── Pass 1 Provenance (confidence_scorer.py):
    │     ├── Per-field confidence based on HOW value was extracted:
    │     │     0.93 → explicit "CARC: 50" label form
    │     │     0.92 → "Date of Denial: …" labeled pattern
    │     │     0.88 → labeled financial pattern
    │     │     0.87 → labeled identifier regex
    │     │     0.75–0.82 → reliable but less-specific patterns
    │     │     0.50 → positional currency fallback
    │     │     0.0  → not found
    │     └── Populates claim.provenance[field] = FieldProvenance(value, extractor, confidence)
    │
    ├── Pass 2 — LLM Extractor (extract_pass2):
    │     ├── Sends structured prompt to LLM (OpenAI gpt-4o-mini)
    │     ├── Extracts: patient_full_name, treating_provider_name, denial_reason_narrative,
    │     │             plan_provision_cited, clinical_criteria_cited, appeal contacts,
    │     │             labeled financial amounts with per-field confidence keys
    │     └── Returns <field>_confidence keys (0.0–1.0) alongside values
    │
    ├── Pass 2 Provenance Update:
    │     └── Upgrades provenance where LLM confidence > existing regex confidence
    │
    ├── Cross-Validation (cross_validate_field):
    │     ├── For 7 key fields (dates, amounts, claim ref): compare Pass 1 vs Pass 2
    │     ├── Agreed → confidence = 0.97 (cross-validated)
    │     └── Disagreed → confidence = 0.50, disputed_values = [p1_val, p2_val]
    │
    └── Returns: ClaimObject, ExtractionConfidence (weighted overall + per-field),
                 warnings (disputed fields, unclassified docs), document_types map
    │
    ▼
[4] BLOCKING FIELD CHECK
    check_blocking_fields(claim) — api/errors.py
    │
    ├── Returns HTTP 422 with ClaimGap if any blocking field is missing:
    │     • date_of_denial          (needed for deadline calculation)
    │     • denial_reason_narrative (needed for appeal letter)
    │     • claim_reference_number  (needed for insurer correspondence)
    │     • regulation_type         (needed to select correct appeal rules)
    └── can_proceed_partial = True if ONLY regulation_type is missing
    │
    ▼
[5] ORCHESTRATED ANALYSIS
    POST /api/v1/claims/analyze (sync) or /analyze/stream (SSE)
    │
    ├── Stage 0: Pre-classify root cause (needed before parallel agents launch)
    │     classify_root_cause(claim):
    │       1. CARC rule classification (deterministic, disjoint buckets):
    │            Prior auth  (CARC 15, 197, 246, 251)     → score +3 (+1 if CO prefix)
    │            Med nec     (CARC 50, 56, 58, 146...)     → score +3
    │            Coding/bill (CARC 4, 6, 9, 11, 16, 18…)  → score +2
    │            Network     (CARC 109, 119, 151, 204)     → score +2
    │            Eligibility (CARC 27, 96, 116, 133)       → score +2
    │            Procedural  (CARC 29, 252, 253, 254)      → score +1
    │       2. If confidence < 0.75 OR no CARC codes → LLM classification
    │       3. Returns higher-confidence result
    │
    ├── Stage 1: Three agents run in PARALLEL (asyncio.gather, return_exceptions=True)
    │   ├── Code Lookup Agent (timeout: 15s)
    │   │     ├── ICD-10 codes  → CMS / NLM API
    │   │     ├── CPT codes     → CMS / NLM HCPCS API
    │   │     ├── HCPCS codes   → CMS HCPCS API
    │   │     ├── CARC/RARC     → local table (carc_rarc_lookup.py, 50+ codes)
    │   │     ├── NPI           → NPPES NPI Registry API
    │   │     ├── Unfound codes → Google Custom Search fallback
    │   │     ├── SQLite cache  → avoids repeat API calls
    │   │     └── Returns: CodeLookupResult with plain_english, common_fix, source per code
    │   │
    │   ├── Regulation Agent (timeout: 20s)
    │   │     ├── ERISA plans   → DOL EBSA §503, eCFR 29 CFR §2560.503-1
    │   │     ├── ACA plans     → eCFR 45 CFR §147.136 (§2719), internal/external review
    │   │     ├── Medicaid      → eCFR 42 CFR §431.220 (fair hearing rules)
    │   │     ├── Med necessity → CMS National Coverage Determinations database
    │   │     └── Returns: applicable_laws[], appeal_process, deadline_days, external_review
    │   │
    │   └── State Rules Agent (timeout: 20s)
    │         ├── Loads state_appeal_rules.json + state_doi_contacts.json
    │         ├── Looks up state by plan_jurisdiction (2-letter code)
    │         ├── Determines regulatory routing: DOL EBSA vs. state DOI vs. Medicaid
    │         └── Returns: StateRulesEnrichment with StateDeadlines (structured model)
    │
    │   Agent failure handling:
    │     timeout → status = "timeout", substitute empty default, pipeline continues
    │     error   → status = "error",   substitute empty default, pipeline continues
    │     OrchestratorResult.agent_status = {"code_lookup_agent": "ok|timeout|error", ...}
    │
    ├── Stage 2: Analysis Agent (timeout: 30s, sequential)
    │     Step 1: Reuse root_cause from Stage 0 (no second LLM call)
    │     Step 2: Denial letter completeness check (deterministic):
    │               ACA §2719 / ERISA §503 required element audit
    │               8 required fields, critical fields weighted 2×
    │               score < 0.75 → deficient = True → escalation_available
    │     Step 3: Preliminary severity triage (pre-deadline)
    │     Step 4: Deadline calculation:
    │               ERISA: internal appeal 60–180 days, external review if non-grandfathered
    │               ACA:   internal 180 days, external review mandatory
    │               Medicaid: fair hearing 90 days
    │               Generates ICS calendar events (with 30-day and 7-day reminders)
    │     Step 5: Refined severity triage using deadline proximity:
    │               Urgent          → deadline < 14 days OR denied amount > $5,000
    │               Time-sensitive  → deadline < 30 days
    │               Routine         → otherwise
    │     Step 6: Approval probability score (0–100%):
    │               Base rates by root cause category
    │               Modifiers: completeness score, regulation type, CARC codes
    │               LLM-provided explanation and per-factor breakdown
    │     Step 7: Financial reconciliation (3 equations, $1 tolerance):
    │               patient_responsibility ≈ copay + coinsurance + deductible
    │               insurer_paid + patient_responsibility ≈ allowed_amount
    │               implied_adjustment = billed − allowed − denied (must be ≥ 0)
    │     Step 8: Validation loop — unresolved code quality check:
    │               > 50% unresolved codes → requires_review = True
    │               Per-code assumption emitted for each unresolved code
    │     Step 9: Build assumptions list (plan type, regulation, denial date, root cause,
    │               ACA compliance, financial discrepancies, unresolved codes)
    │
    └── Returns: OrchestratorResult
                  claim_object, enrichment, analysis, sources,
                  errors, agent_status, llm_available
    │
    ▼
[6] OUTPUT GENERATION
    POST /api/v1/outputs/*  (each called separately by frontend)
    │
    ├── /summary          → plain-English denial explanation (patient reading level)
    ├── /action-checklist → numbered steps with "why is this required?" expanders
    ├── /appeal-letter    → formal letter with regulation citations + clinical facts
    │                        + provider_message + insurer_message (3 tabs)
    ├── /provider-brief   → one-page summary for treating physician
    ├── /deadlines        → structured deadline list with ICS data embedded
    ├── /completeness     → field-by-field denial letter completeness checklist
    ├── /routing-card     → ERISA vs. state DOI routing card with contact blocks
    ├── /assumptions      → assumptions panel with confidence, impact, verification tips
    └── /probability      → detailed probability breakdown with per-factor explanations
    │
    ▼
[7] EXPORT
    ├── POST /export/pdf  → markdown → PDF via fpdf2 (appeal_letter / provider_brief / summary)
    └── POST /export/ics  → .ics calendar file with configurable reminders (default 30 + 7 days)
```

---

## 5. Module Deep-Dives

### 5.1 Extraction Layer

#### `extraction/pdf_extractor.py`
Handles file-type detection and text extraction.

| Document Type | Detection | Strategy |
|---|---|---|
| `pdf_digital` | pdfplumber extracts ≥ 50 chars | pdfplumber → PyMuPDF fallback |
| `pdf_scanned` | All pages: chars < 30 AND has images | `needs_client_ocr = True` |
| `pdf_mixed` | Some pages digital, some scanned | Digital pages extracted; scanned pages listed in `scanned_page_numbers` |
| `image` | File extension is jpg/png/webp/tiff | `needs_client_ocr = True` |

Per-page analysis produces `PageMeta(page_number, text_chars, has_images, is_scanned)`. Tables are extracted in structured form (`ExtractionResult.tables`) and also appended as tab-separated text.

#### `extraction/document_stitcher.py` (v2)
Classifies and merges multiple uploaded documents into one `ClaimObject`.

**Classification** uses weighted feature-scoring with compiled regex rules:
- `"right to appeal"` in text → denial_letter +4 points
- `"explanation of benefits"` → eob +5 points
- Confidence = `(winner_score − runner_up_score) / winner_score`
- Below 0.30 threshold → classified as `"requires_review"`

**Authority rules** (which document wins each field group):
```
denial_letter → claim ID, denial date, denial reason, appeal rights, NPI
eob           → CARC/RARC codes, financial amounts, ICD-10, CPT, HCPCS
hospital_bill → facility name, itemized charges
insurance_card → member ID, group number, plan name
```

**Claim-ID consistency** warns when uploaded documents have different `claim_reference_number` values.

#### `extraction/regex_extractor.py`
Pass 1 deterministic extraction using compiled regular expressions.

| Field | Pattern Type | Confidence |
|---|---|---|
| `date_of_denial` | Labeled ("Date of Denial: MM/DD/YYYY") | 0.92 |
| `carc_codes` | Explicit ("CARC: 50") or group form ("CO-50") | 0.90–0.93 |
| `claim_reference_number` | Labeled ("Claim #: ABC123") | 0.87 |
| Financial amounts | Labeled ("Billed: $1,234") | 0.88 |
| Financial amounts | Positional currency | 0.50 |
| ICD-10 codes | Structural validation (letter + 2-7 digits + decimal) | 0.78 |
| NPI | Luhn algorithm validated | 0.85 |

#### `extraction/llm_extractor.py`
Pass 2 LLM-powered extraction. Extracts contextual entities that regex cannot reliably find: names, narratives, denial reason text, labeled amounts, appeal contact information. Returns per-field `<field>_confidence` keys (0.0–1.0) for use in cross-validation.

#### `extraction/confidence_scorer.py`
Feature-based per-field confidence scoring.

| Score | Meaning |
|---|---|
| 0.97 | Cross-validated: Pass 1 and Pass 2 agree within tolerance |
| 0.92–0.93 | Verbatim labeled pattern (e.g., `"Date of Denial: …"`) |
| 0.85–0.90 | Well-structured pattern or LLM extraction |
| 0.75–0.82 | Reliable but less-specific patterns |
| 0.50 | Disputed (Pass 1 ≠ Pass 2) or positional fallback |
| 0.0 | Field not found |

`cross_validate_field(field, p1_value, p2_value)` normalizes values before comparison:
- Dates → `date` objects
- Amounts → floats with $1.00 tolerance
- Strings → lowercased and stripped

---

### 5.2 Agent Layer

#### `agents/orchestrator.py`
Central coordinator. Runs all agents with per-agent timeouts and graceful degradation.

```
Stage 0 → classify_root_cause()          [needed by regulation agent]
Stage 1 → asyncio.gather([               [parallel, return_exceptions=True]
    code_lookup_agent  (15s timeout),
    regulation_agent   (20s timeout),
    state_rules_agent  (20s timeout),
])
Stage 2 → analysis_agent                 [sequential, 30s timeout]
```

Failed agents substitute empty defaults (`CodeLookupResult()`, `RegulationEnrichment()`, `StateRulesEnrichment()`). The pipeline always returns a result, even if some agents timed out. `OrchestratorResult.agent_status` maps each agent name to `"ok" | "timeout" | "error"`.

Supports both synchronous (`run_orchestrator`) and streaming (`stream_orchestrator` via SSE) modes. Streaming yields 6 events: `started`, `codes_enriched`, `regulations_enriched`, `state_rules_enriched`, `analysis_complete`, `done`.

#### `agents/code_lookup_agent.py`
Resolves all codes found in the claim against authoritative sources.

| Code Type | Source | Cached |
|---|---|---|
| ICD-10 | CMS / NLM ICD-10-CM API | Yes (SQLite) |
| CPT | CMS / NLM HCPCS API | Yes (SQLite) |
| HCPCS | CMS HCPCS API | Yes (SQLite) |
| CARC | Local table (`carc_rarc_lookup.py`) | N/A |
| RARC | Local table | N/A |
| NPI | NPPES NPI Registry API (live) | Yes (SQLite) |
| Unfound | Google Custom Search (last resort) | No |

Each resolved code returns: `description`, `plain_english` (patient-facing), `common_fix`, `source`, `source_url`, `found` (bool).

#### `agents/regulation_agent.py`
Fetches applicable federal regulations from live APIs.

| Plan Type | Regulation | Source |
|---|---|---|
| ERISA | 29 CFR §2560.503-1 (60–180 day appeal) | eCFR.gov API |
| ACA / Fully Insured | 45 CFR §147.136 §2719 (180 day appeal, external review) | eCFR.gov API |
| Medicaid | 42 CFR §431.220 (90 day fair hearing) | eCFR.gov API |
| Medical necessity denial | CMS National Coverage Determinations | CMS Coverage DB |

Returns: `applicable_laws[]`, `appeal_process` steps, `internal_appeal_deadline_days`, `external_review_available`, `required_notice_elements`, `coverage_determination`.

#### `agents/state_rules_agent.py`
Provides state-specific appeal rules and routing information.

- Loads `data/state_appeal_rules.json` (50 states) and `data/state_doi_contacts.json`
- Determines `regulatory_routing`: DOL EBSA (ERISA) or State DOI (fully insured) or Medicaid agency
- Returns structured `StateDeadlines(internal_appeal_days, external_review_days, expedited_hours, regulation_basis)`

#### `agents/analysis_agent.py`
Sequential analysis pipeline. 9-step process (see workflow section above). Returns `AnalysisResult`:
- `root_cause` — category, confidence, responsible_party, reasoning, classification_method
- `denial_completeness` — score, missing_fields, present_fields, escalation_available
- `deadlines` — internal_appeal, external_review, expedited (with days_remaining, already_passed)
- `approval_probability` — score (0–1), reasoning, per-factor breakdown
- `severity_triage` — "urgent" | "time_sensitive" | "routine"
- `assumptions` — list of {assumption, confidence, impact} dicts
- `ics_events` — calendar events for each deadline
- `financial_reconciliation` — reconciled, discrepancies, implied_adjustment
- `requires_review` — True when > 50% of codes are unresolved

#### `agents/output_agent.py`
LLM-driven content generation. Uses `complete_llm()` with structured prompts.

| Output | Content |
|---|---|
| `plain_english_summary` | One-paragraph denial explanation at patient reading level |
| `action_checklist` | Numbered steps with collapsible "why is this required?" explanations |
| `appeal_letter` | Formal letter citing specific regulations, clinical facts, and code meanings |
| `provider_message` | Letter to billing office (retroactive auth, corrected codes, etc.) |
| `insurer_message` | Message to member services |
| `provider_brief` | One-page summary for treating physician |

Includes JSON repair logic (`_repair_truncated_json`) to handle LLM truncation.

---

### 5.3 Analysis Layer

#### `analysis/root_cause_classifier.py`
Hybrid rule + LLM classifier. Maps claim data to one of 6 categories:

| Category | CARC Codes (examples) | Score Weight |
|---|---|---|
| `medical_necessity` | 50, 56, 58, 146, 167, 193 | +3 (CO prefix: +4) |
| `prior_authorization` | 15, 197, 246, 251 | +3 (CO prefix: +4) |
| `coding_billing_error` | 4, 6, 9, 11, 16, 18, 22… | +2 |
| `network_coverage` | 109, 119, 151, 204 | +2 |
| `eligibility_enrollment` | 27, 96, 116, 133 | +2 |
| `procedural_administrative` | 29, 252, 253, 254 | +1 |

Rules confidence ≥ 0.75 → returns rules result directly. Otherwise → LLM classification. Takes higher confidence result when both are available.

#### `analysis/completeness_checker.py`
Validates denial letters against ACA §2719 / ERISA §503 required elements:

1. Specific reason for denial
2. Reference to specific plan provision
3. Scientific/clinical evidence
4. Description of internal appeal process
5. Notice of external review rights
6. Notice of state DOI complaint rights
7. Contact info for insurer appeals
8. Clinical criteria statement (for medical necessity denials)

Critical fields (denial reason, clinical criteria) are weighted 2×. Score < 0.75 → `deficient = True` → `escalation_available` (insurer may have violated ACA/ERISA requirements).

#### `analysis/deadline_calculator.py`
Calculates exact appeal deadline dates from `date_of_denial` + regulation type.

| Regulation | Internal Appeal | External Review | Expedited |
|---|---|---|---|
| ERISA | 60–180 days | If non-grandfathered | 72 hours |
| ACA (fully insured) | 180 days | Mandatory | 72 hours |
| Medicaid | 90 days (fair hearing) | State court | N/A |

Produces `ics_events[]` with VCALENDAR data and configurable alarm triggers (30-day and 7-day defaults).

#### `analysis/probability_estimator.py`
Estimates 0–100% likelihood of appeal success based on:
- Base rate by root cause category (medical necessity ~45%, coding errors ~65%, prior auth ~50%)
- Completeness score modifier (deficient denial letter = +10–15%)
- Regulation type modifier
- Specific CARC/RARC code context

#### `analysis/severity_triage.py`
Classifies urgency:
- `urgent` → deadline < 14 days OR denied amount > threshold
- `time_sensitive` → deadline < 30 days
- `routine` → otherwise

#### `analysis/financial_reconciliation.py`
Verifies EOB math with $1.00 tolerance:
1. `patient_responsibility_total ≈ copay + coinsurance + deductible`
2. `insurer_paid + patient_responsibility ≈ allowed_amount`
3. `implied_adjustment = billed − allowed − denied` (flag if negative)

Each discrepancy becomes an assumption with confidence and impact level.

#### `analysis/validation_loop.py`
Post-code-lookup quality gate. Counts unresolved codes and emits per-code assumptions with plain-English hints. Triggers `requires_review = True` at > 50% unresolved rate.

---

### 5.4 API Routes

#### `api/routes/wizard.py`
Regulatory routing logic based on plan type answers.

| Input | Output |
|---|---|
| `employer` + `erisa` | ERISA routing → DOL EBSA |
| `employer` + `fully_insured` | State routing → State DOI |
| `employer` + `unknown` + size 1000+ | Assumed ERISA (~80% of large employers) |
| `employer` + `unknown` + smaller | Assumed fully insured (~60% of employer plans) |
| `marketplace` | State ACA routing → State DOI |
| `medicaid` | Medicaid → CMS + state agency |
| `individual` | State ACA routing → State DOI |
| Any with ERISA §503 in denial letter | Override to ERISA regardless of wizard answer |

Fetches live applicable laws from eCFR at request time via `regulatory_fetch.py`. Returns `regulation_type_source` ("user" / "extracted" / "defaulted") for the assumptions panel.

#### `api/routes/extract.py`
Runs the full two-pass extraction pipeline and provenance tracking:
1. Stitch documents → classify → merge
2. Pass 1 regex extraction
3. Populate Pass 1 provenance
4. Pass 2 LLM extraction (skipped if no LLM configured)
5. Update provenance from LLM results
6. Cross-validate key fields
7. Compute weighted ExtractionConfidence

#### `api/routes/ocr.py`
`POST /api/v1/documents/ocr/page` — server-side OCR fallback.
- Accepts PNG/JPEG image upload
- Runs `pytesseract.image_to_data()`
- Returns `{text, confidence, engine: "pytesseract"}`
- Returns HTTP 501 if pytesseract is not installed

#### `api/errors.py`
Defines `ClaimGap` — structured 422 response when blocking fields are missing. Four blocking fields with regulation basis, `where_to_look` guidance, and `can_proceed_partial` flag.

---

### 5.5 Tools Layer

| Tool | Purpose | External API |
|---|---|---|
| `llm_client.py` | Unified async LLM client with rate limiting, fallback chain, priority queue | OpenAI / Ollama |
| `carc_rarc_lookup.py` | CARC/RARC code descriptions with plain English + common fix (50+ codes) | Local table |
| `cms_icd_lookup.py` | ICD-10 diagnosis code lookup | CMS / NLM |
| `cms_hcpcs_lookup.py` | CPT/HCPCS procedure code lookup | CMS |
| `npi_registry.py` | Provider NPI lookup | NPPES NPI Registry |
| `ecfr_search.py` | Federal regulation text retrieval | eCFR.gov API |
| `erisa_search.py` | ERISA §503 appeal rules | DOL EBSA |
| `aca_search.py` | ACA §2719 external review rules | eCFR.gov |
| `cms_coverage.py` | National Coverage Determinations for medical necessity | CMS |
| `idoi_search.py` | Indiana DOI resources (Indiana-first focus) | IDOI |
| `state_doi_lookup.py` | 50-state DOI contact lookup | Local JSON |
| `regulatory_fetch.py` | Fetch applicable laws by profile (erisa/state_aca/medicaid) | eCFR |
| `code_cache.py` | SQLite-backed cache for code lookups (avoids repeat API calls) | Local |
| `web_search.py` | Google Custom Search fallback for unfound codes | Google CSE API |

---

## 6. API Reference

All routes are prefixed `/api/v1`. Rate limits apply per IP.

### Document Routes (`/documents`)

| Method | Path | Rate Limit | Description |
|---|---|---|---|
| POST | `/upload` | 10/min | Upload up to 5 files; returns `upload_id` and per-doc extraction results |
| POST | `/extract` | — | Run two-pass extraction pipeline; returns `ClaimObject` and `ExtractionConfidence` |
| POST | `/ocr/page` | — | Server-side OCR on single page image; returns `text` + `confidence` |

### Wizard Routes (`/wizard`)

| Method | Path | Rate Limit | Description |
|---|---|---|---|
| POST | `/plan-type` | 20/min | Determine regulatory framework from plan type answers |

### Analysis Routes (`/claims`)

| Method | Path | Rate Limit | Description |
|---|---|---|---|
| POST | `/analyze` | 5/min | Full synchronous analysis; returns complete `OrchestratorResult` in ~8–16s |
| POST | `/analyze/stream` | 5/min | SSE streaming analysis; yields 6 progress events |

**SSE Event Types:**
```
started             → pipeline has begun
codes_enriched      → code lookup complete (with code count)
regulations_enriched → regulation agent complete (deadline days, external review)
state_rules_enriched → state rules agent complete (state, routing, DOI)
analysis_complete   → analysis done (root cause, probability, severity, deadlines)
done                → full combined response (same payload as /analyze)
error               → pipeline failed
```

### Output Routes (`/outputs`)

| Method | Path | LLM Required | Description |
|---|---|---|---|
| POST | `/summary` | Yes | Plain-English denial summary |
| POST | `/action-checklist` | Yes | Numbered steps with why-expanders |
| POST | `/appeal-letter` | Yes | Appeal letter + provider/insurer messages |
| POST | `/provider-brief` | Yes | One-page physician summary |
| POST | `/deadlines` | No | Structured deadlines with embedded ICS data |
| POST | `/completeness` | No | ACA/ERISA completeness checklist |
| POST | `/routing-card` | Yes | Regulatory routing card |
| POST | `/assumptions` | No | Assumptions panel with guidance |
| POST | `/probability` | No | Probability breakdown with per-factor detail |

### Export Routes (`/export`)

| Method | Path | Description |
|---|---|---|
| POST | `/pdf` | Generate PDF (appeal_letter / provider_brief / summary) from markdown |
| POST | `/ics` | Generate .ics calendar file with configurable reminders |

### Code Routes (`/codes`)

| Method | Path | Description |
|---|---|---|
| GET | `/lookup` | Live code lookup by type and code value |

---

## 7. Data Model — ClaimObject

The central data structure that flows through the entire pipeline from extraction → enrichment → analysis → output.

```
ClaimObject
├── upload_id: str                          # Session identifier (UUID)
├── source_documents: list[str]             # doc_ids
│
├── identification: ClaimIdentification
│   ├── claim_reference_number: str
│   ├── date_of_service: date
│   ├── date_of_denial: date               # Critical field (triggers deadline calc)
│   ├── date_of_eob: date
│   ├── plan_policy_number: str
│   ├── group_number: str
│   ├── plan_type: PlanType                # employer_erisa | employer_fully_insured |
│   │                                      # marketplace | medicaid | individual
│   ├── plan_jurisdiction: str             # 2-letter state code
│   ├── erisa_or_state_regulated: RegulationType  # erisa | state | medicaid | unknown
│   └── regulation_type_source: str        # user | extracted | defaulted
│
├── patient_provider: PatientProviderEntities
│   ├── patient_full_name: str
│   ├── patient_member_id: str
│   ├── patient_dob: date
│   ├── treating_provider_name: str
│   ├── treating_provider_npi: str         # Luhn-validated
│   ├── treating_provider_specialty: str
│   ├── facility_name: str
│   ├── facility_address: str
│   └── network_status: str               # "in-network" | "out-of-network"
│
├── service_billing: ServiceBillingEntities
│   ├── icd10_diagnosis_codes: list[str]
│   ├── cpt_procedure_codes: list[str]
│   ├── hcpcs_codes: list[str]
│   ├── procedure_description: str
│   ├── service_date_range: str
│   ├── place_of_service_code: str
│   ├── units_of_service: int
│   ├── modifier_codes: list[str]
│   └── unverified_codes: list[str]       # Excluded from appeal letter citations
│
├── financial: FinancialEntities
│   ├── billed_amount: float
│   ├── allowed_amount: float
│   ├── insurer_paid_amount: float
│   ├── denied_amount: float
│   ├── patient_responsibility_total: float
│   ├── copay_amount: float
│   ├── coinsurance_amount: float
│   ├── deductible_applied: float
│   └── out_of_pocket_remaining: float
│
├── denial_reason: DenialReasonEntities
│   ├── carc_codes: list[str]
│   ├── rarc_codes: list[str]
│   ├── carc_codes_with_group: dict[str, str]  # {"50": "CO", "1": "PR"}
│   ├── denial_reason_narrative: str
│   ├── plan_provision_cited: str
│   ├── clinical_criteria_cited: str
│   ├── medical_necessity_statement: str
│   ├── prior_auth_status: str            # required_not_obtained | approved | denied
│   └── prior_auth_number: str
│
├── appeal_rights: AppealRightsEntities
│   ├── internal_appeal_deadline_stated: str
│   ├── external_review_deadline_stated: str
│   ├── expedited_review_available: bool
│   ├── insurer_appeals_contact_name: str
│   ├── insurer_appeals_phone: str
│   ├── insurer_appeals_address: str
│   ├── insurer_appeals_fax: str
│   └── state_commissioner_info_present: bool
│
├── derived: DerivedEntities              # Filled exclusively by Analysis Agent
│   ├── root_cause_category: RootCauseCategory
│   ├── responsible_party: str           # patient | provider_billing_office | insurer | unknown
│   ├── denial_completeness_score: float  # 0.0–1.0
│   ├── appeal_deadline_internal: date
│   ├── appeal_deadline_external: date
│   ├── appeal_deadline_expedited: date
│   ├── approval_probability_score: float # 0.0–1.0
│   └── severity_triage: SeverityTriage  # urgent | time_sensitive | routine
│
└── provenance: dict[str, FieldProvenance]
    └── field_name → FieldProvenance:
        ├── value: Any
        ├── source_doc_id: str
        ├── extractor: str               # regex | llm | user | missing | unknown
        ├── confidence: float            # 0.0–1.0
        ├── source_url: str
        └── disputed_values: list[Any]  # [p1_val, p2_val] when Pass1 ≠ Pass2
```

---

## 8. External Data Sources

The system never uses a static local knowledge base for regulatory or code data. Everything is fetched live from authoritative sources at analysis time.

| Data | Source | Why Live |
|---|---|---|
| ICD-10 diagnosis codes | CMS / NLM ICD-10-CM API | Codes update annually |
| CPT / HCPCS procedure codes | CMS / NLM HCPCS API | AMA updates quarterly |
| CARC / RARC denial codes | Local table (carc_rarc_lookup.py) | No public API exists |
| Provider NPI | NPPES NPI Registry | Provider data changes frequently |
| ERISA §503 rules | eCFR.gov (29 CFR §2560.503-1) | Regulations change |
| ACA §2719 appeal rules | eCFR.gov (45 CFR §147.136) | Key appeal timelines |
| Medicaid fair hearing rules | eCFR.gov (42 CFR §431.220) | State variation |
| CMS National Coverage Determinations | CMS Coverage Database | Med-necessity only |
| State DOI contacts | Static JSON (50 states) | Rarely changes |
| State appeal rules | Static JSON (50 states) | Rarely changes |
| Unfound codes | Google Custom Search API | Last-resort fallback |

**Caching:** Code lookups are cached in SQLite (`data/code_cache.sqlite`) to avoid redundant API calls within a session. Cache invalidation is not time-based — stale entries must be manually cleared if needed.

---

## 9. LLM Client & Fallback Chain

### `tools/llm_client.py`

```
Primary:  OpenAI gpt-4o-mini  (configurable via OPENAI_MODEL_PRIMARY)
Fallback: OpenAI gpt-4o       (configurable via OPENAI_MODEL_FALLBACK)
Local:    Ollama (llama3.2)   (only when OLLAMA_ENABLED=true)
```

**Rate limiting strategy:**
- `asyncio.PriorityQueue` — lower priority number = runs first
  - Priority 1 (highest): Root cause classification, extraction
  - Priority 2: Analysis agents
  - Priority 3 (lowest): Output generation
- Per-model cooldown: one model getting 429 does not pause other models
- Exponential backoff on 429 errors
- `LLM_MAX_CONCURRENT_REQUESTS = 3` (configurable)
- `LLM_MIN_DELAY_BETWEEN_REQUESTS = 0.1s`

**`is_llm_available()`** — checks if any LLM is configured. Output routes return HTTP 200 with `{status: "llm_unavailable"}` instead of 503 when no LLM is configured, allowing the frontend to gracefully handle deterministic-only mode.

**LLM tasks:**
1. Pass 2 extraction (names, narratives, amounts with confidence)
2. Root cause disambiguation (when CARC rule confidence < 0.75)
3. Output generation (all 6 output types)

All code lookups, regulation fetches, deadline calculations, completeness checks, probability scoring, and routing logic are **deterministic** — no LLM involved.

---

## 10. Features

### Document Processing
- Upload up to 5 documents (PDF, JPG, PNG, WEBP, TIFF), max 10 MB each
- Automatic text extraction from digital PDFs (pdfplumber primary, PyMuPDF fallback)
- Per-page OCR detection: pages with < 30 non-whitespace chars + embedded images → flagged as scanned
- Mixed document support: digital and scanned pages in the same PDF
- Server-side OCR endpoint (`POST /ocr/page`) using pytesseract as fallback to client-side Tesseract.js
- Structured table extraction from PDFs (preserves header→value relationships)
- Multi-document stitching with weighted feature-scoring classification (confidence-aware)
- Claim-ID consistency check across multiple uploaded documents
- Quality-ranking of duplicate document types

### Extraction & Provenance
- Two-pass extraction: deterministic regex (Pass 1) + LLM contextual (Pass 2)
- Per-field confidence scoring (feature-based, not a step function)
- Cross-validation between passes: agreed = 0.97 confidence, disputed = 0.50 + both candidates stored
- Full extraction provenance: every field records its value, extractor, confidence, and source doc
- CARC group prefix extraction (CO-, PR-, OA-, PI-, CR-) for responsible-party inference

### Code Analysis
- Live lookup of ICD-10, CPT, HCPCS, CARC, RARC, and NPI codes
- Plain-English patient-facing descriptions for every code
- "Common fix" guidance for denial codes
- Source citation (CMS, NLM, NPPES, WPC)
- Unresolved code tracking (excluded from appeal letter citations)
- SQLite caching to avoid redundant API calls

### Regulatory Intelligence
- Automatic ERISA vs. ACA vs. Medicaid routing from plan type wizard
- ERISA §503 citation override: if denial letter cites ERISA, overrides wizard answer
- Bayesian employer size heuristic (1000+ employees → assume ERISA, ~80% base rate)
- Live federal regulation text from eCFR.gov at analysis time
- CMS National Coverage Determinations for medical necessity denials
- 50-state DOI contact database with complaint URLs and external review links

### Analysis & Scoring
- Root cause classification across 6 categories (CARC rules + LLM hybrid)
- CO-prefix bonus in CARC scoring (contractual obligation = stronger signal)
- Denial letter completeness check against ACA §2719 / ERISA §503 required elements (8 fields, weighted)
- Appeal probability score with per-factor explanation
- Deadline calculation for internal appeal, external review, and expedited review
- Severity triage: Urgent / Time-Sensitive / Routine
- Financial reconciliation: 3 EOB math equations with $1.00 tolerance
- Validation loop: code resolution quality check with requires_review flag
- Assumptions panel: explicit list of all assumptions with confidence and impact levels
- Blocking field check: structured 422 response with regulation basis and where-to-look guidance

### Generated Outputs
- Plain-English denial summary (patient reading level)
- Recovery roadmap: numbered action steps with "why is this required?" expandable explanations
- Appeal letter: formal letter citing specific regulations, code meanings, and clinical facts
- Provider message: request to billing office
- Insurer message: message to member services
- Provider brief: one-page summary for treating physician
- Regulatory routing card: which regulator governs this plan, contact info, process steps
- Denial letter completeness checklist (field-by-field with legal citation and action)
- Probability breakdown with base rates and per-factor modifiers

### Export
- PDF download (appeal letter, provider brief, or denial summary) via fpdf2
  - Markdown → formatted PDF with h1/h2/h3/body/bullet rendering
  - Latin-1 safe (normalizes common Unicode from LLM output)
- Calendar export (.ics) with configurable reminder days (default 30-day and 7-day reminders)
  - Compatible with Google Calendar, Outlook, Apple Calendar

### Infrastructure
- Docker + docker-compose for full-stack containerized deployment
- SSE streaming endpoint for progressive frontend rendering
- Per-agent timeouts (15–30s) with graceful degradation
- Rate limiting (slowapi) per IP per endpoint
- Priority queue-based LLM dispatch (analysis > output generation)
- Per-model rate limit cooldown (one model 429 doesn't pause others)
- Health check endpoint (`/health` and `/api/v1/health`) for load balancers and monitoring
- CORS configured for localhost dev and `*.vercel.app` production

---

## 11. Configuration & Deployment

### Environment Variables (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | `""` | Primary LLM (required for LLM features) |
| `OPENAI_MODEL_PRIMARY` | `gpt-4o-mini` | Primary model |
| `OPENAI_MODEL_FALLBACK` | `gpt-4o` | Fallback model |
| `OPENAI_BASE_URL` | `""` | Override base URL (Groq, etc.) |
| `OLLAMA_ENABLED` | `false` | Enable local Ollama fallback |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model |
| `MAX_FILE_SIZE_MB` | `10` | Per-file upload limit |
| `MAX_FILES_PER_UPLOAD` | `5` | Files per upload request |
| `RATE_LIMIT_PER_MINUTE` | `10` | Global rate limit |
| `LLM_MAX_CONCURRENT_REQUESTS` | `3` | Concurrent LLM calls |
| `LLM_RETRY_ON_RATE_LIMIT` | `true` | Retry on 429 |
| `LLM_MIN_DELAY_BETWEEN_REQUESTS` | `0.1` | Min seconds between LLM calls |
| `GOOGLE_SEARCH_API_KEY` | `""` | Fallback code lookup |
| `GOOGLE_SEARCH_CX` | `""` | Google Custom Search engine ID |
| `GOOGLE_VISION_API_KEY` | `""` | Reserved (Google Vision OCR, not yet used) |
| `DEBUG` | `false` | Enables Ollama in non-development mode |

### Startup

```bash
# Local development
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add API keys
uvicorn main:app --reload  # http://localhost:8000

# Docker
cp backend/.env.example backend/.env
docker-compose up --build
# Frontend → http://localhost | Backend → http://localhost:8000
```

### Production Deployment
- **Backend**: Render (Docker runtime, health check `/health`)
- **Frontend**: Vercel (Vite preset, root directory: `frontend`)
- **Required env vars**: `OPENAI_API_KEY` (or compatible provider key via `OPENAI_BASE_URL`)

### Limitations
- No database — results are session-scoped (browser only)
- Scanned document OCR is client-side by default (server-side requires `pytesseract` install)
- Indiana state resources most complete (IDOI); all 50 states have DOI contacts but regulatory depth varies
- Not legal advice — outputs are informational; complex cases should involve a patient advocate or attorney
