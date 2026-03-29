# CBH – Insurance Claim & Billing Debugger
## Implementation Status & Architecture Reference

> **Generated:** 2026-03-29
> **Codebase:** `/Users/athish/Documents/ClaudeHackathon`
> **Product name (frontend):** Resolvly
> **Repo:** https://github.com/Ctrl-Alt-Defeat-Hackathon/CBH

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Technology Stack (Actual)](#2-technology-stack-actual)
3. [Backend Architecture](#3-backend-architecture)
4. [End-to-End Pipeline Flow](#4-end-to-end-pipeline-flow)
5. [API Reference — All Endpoints](#5-api-reference--all-endpoints)
6. [Agent Architecture & Interactions](#6-agent-architecture--interactions)
7. [Data Model: ClaimObject](#7-data-model-claimobject)
8. [Extraction Pipeline (Phases 1 & 2)](#8-extraction-pipeline-phases-1--2)
9. [Orchestrator & Parallel Agent Execution](#9-orchestrator--parallel-agent-execution)
10. [Analysis Modules](#10-analysis-modules)
11. [Output Generation](#11-output-generation)
12. [Frontend Architecture](#12-frontend-architecture)
13. [Frontend Session Storage & Caching](#13-frontend-session-storage--caching)
14. [Frontend Routes & Pages](#14-frontend-routes--pages)
15. [LLM Configuration & Fallback Chain](#15-llm-configuration--fallback-chain)
16. [External Tool Integrations](#16-external-tool-integrations)
17. [Export Pipeline](#17-export-pipeline)
18. [Rate Limiting & Security](#18-rate-limiting--security)
19. [Key Architectural Decisions](#19-key-architectural-decisions)

---

## 1. System Overview

Resolvly is a fully stateless, AI-powered insurance claim analysis platform. A patient uploads up to three insurance documents (Denial Letter, EOB, Medical Bill), answers two context questions about their plan type, and the system:

1. Extracts all entities from the documents (two-pass: regex + LLM)
2. Live-looks up every medical/billing code against authoritative public APIs (CMS, NPPES, WPC)
3. Fetches the applicable federal regulations (eCFR, ERISA, ACA, CMS Coverage Database)
4. Fetches state DOI contact and routing rules for all 50 states
5. Runs root-cause classification, deadline calculation, completeness scoring, and approval probability estimation
6. Generates patient-facing outputs: plain-English summary, action checklist, appeal letter, provider brief, routing card
7. Allows PDF and .ics calendar export of results

The system has **no database and no user accounts**. All state flows through `sessionStorage` in the browser for the duration of the session.

---

## 2. Technology Stack (Actual)

| Layer | Technology | Notes |
|---|---|---|
| Backend framework | FastAPI (Python) | Async, with SlowAPI rate limiting |
| LLM (primary) | Groq – `llama-3.3-70b-versatile` | OpenAI-compatible, fast inference |
| LLM (fallback 1) | Groq – `llama-3.1-8b-instant` | Smaller/faster fallback |
| LLM (fallback 2) | Google Gemini 2.5 Flash | `gemini-2.5-flash` |
| LLM (fallback 3) | Gemini 2.5 Flash Lite | `gemini-2.5-flash-lite` |
| LLM (dev-only) | Ollama `llama3.2` | `ollama_enabled=False` by default |
| PDF extraction | pdfplumber (primary) + PyMuPDF (fallback) | Server-side for digital PDFs |
| OCR (scanned PDFs) | Client-side Tesseract.js | Backend flags `needs_client_ocr=True` |
| PDF export | fpdf2 | Generates PDFs from markdown content |
| Frontend framework | React 18 + Vite + React Router v6 | TypeScript |
| Styling | Tailwind CSS + shadcn/ui | Material Symbols icons |
| Deployment target | Render (backend, free tier) / Vercel (frontend) | |
| Static data | `data/state_doi_contacts.json` | All 50 state DOI contacts |

---

## 3. Backend Architecture

```
backend/
├── main.py                          ← FastAPI app, router mounting, CORS, rate-limit setup
├── config.py                        ← Pydantic settings (env vars: GROQ_API_KEY, GEMINI_API_KEY, etc.)
│
├── api/routes/
│   ├── health.py                    ← GET /api/v1/health
│   ├── upload.py                    ← POST /api/v1/documents/upload
│   ├── extract.py                   ← POST /api/v1/documents/extract
│   ├── wizard.py                    ← POST /api/v1/wizard/plan-type
│   ├── analyze.py                   ← POST /api/v1/claims/analyze  (+ /stream SSE)
│   ├── codes.py                     ← GET  /api/v1/codes/lookup
│   ├── outputs.py                   ← POST /api/v1/outputs/* (9 endpoints)
│   └── export.py                    ← POST /api/v1/export/pdf  +  /export/ics
│
├── agents/
│   ├── orchestrator.py              ← Central coordinator; dispatches all agents
│   ├── code_lookup_agent.py         ← ICD-10, CPT, HCPCS, CARC, RARC, NPI lookups
│   ├── regulation_agent.py          ← eCFR, ERISA, ACA, CMS Coverage lookups
│   ├── state_rules_agent.py         ← IDOI/State DOI lookup + routing card
│   ├── analysis_agent.py            ← Root cause, deadlines, probability, completeness
│   └── output_agent.py              ← LLM-generated letters, summaries, checklists
│
├── extraction/
│   ├── schema.py                    ← ClaimObject Pydantic model (central data structure)
│   ├── pdf_extractor.py             ← pdfplumber + PyMuPDF text extraction
│   ├── regex_extractor.py           ← Pass 1: deterministic regex extraction
│   ├── llm_extractor.py             ← Pass 2: LLM-powered entity extraction
│   └── document_stitcher.py         ← Multi-doc stitching + document classification
│
├── analysis/
│   ├── root_cause_classifier.py     ← LLM + heuristic root cause classification
│   ├── deadline_calculator.py       ← Regulation-aware appeal deadline calculation
│   ├── completeness_checker.py      ← Denial letter completeness scoring (ACA/ERISA/Medicaid)
│   ├── severity_triage.py           ← urgent / time_sensitive / routine triage
│   └── probability_estimator.py     ← Approval probability score (0.0–1.0)
│
├── tools/
│   ├── llm_client.py                ← Unified LLM client with Groq→Gemini fallback chain
│   ├── cms_icd_lookup.py            ← CMS/NLM ICD-10-CM API
│   ├── cms_hcpcs_lookup.py          ← CMS/NLM HCPCS/CPT API
│   ├── carc_rarc_lookup.py          ← Local CARC/RARC table (WPC-sourced)
│   ├── npi_registry.py              ← NPPES NPI Registry API
│   ├── ecfr_search.py               ← eCFR.gov API (federal regulations)
│   ├── erisa_search.py              ← ERISA-specific regulation lookup
│   ├── aca_search.py                ← ACA §2719 provision lookup
│   ├── cms_coverage.py              ← CMS National Coverage Database lookup
│   ├── idoi_search.py               ← Indiana DOI + 50-state DOI lookup
│   ├── state_doi_lookup.py          ← Static state DOI contacts from JSON
│   ├── regulatory_fetch.py          ← Live regulatory law fetcher (used by wizard)
│   └── web_search.py                ← Google Custom Search (fallback for unfound codes)
│
└── data/
    └── state_doi_contacts.json      ← All 50 state DOI contact records
```

---

## 4. End-to-End Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND (React/Vite)                            │
│                                                                             │
│   User visits /analyze                                                      │
│   ├── Selects plan type: employer / individual / medicaid                   │
│   ├── Selects funding: ERISA self-funded / Fully Insured                    │
│   └── Uploads 3 files: Denial Letter + EOB + Medical Bill                  │
│                                                                             │
│   Click "Begin Forensic Analysis"                                           │
│   → setPhase('processing')   ← shows animated pipeline progress UI         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: POST /api/v1/documents/upload                                      │
│                                                                             │
│  Input:  multipart/form-data  { files: File[] }  (up to 5 files, 10MB ea.) │
│                                                                             │
│  For each file:                                                             │
│    ├── Validate MIME type / extension (PDF, JPG, PNG, WebP, TIFF)           │
│    ├── pdf_extractor.py:                                                    │
│    │     ├── Digital PDF  → pdfplumber (primary) → PyMuPDF (fallback)       │
│    │     ├── Scanned PDF  → returns needs_client_ocr=True                   │
│    │     └── Image file   → returns needs_client_ocr=True                   │
│    └── Assign doc_id (UUID)                                                 │
│                                                                             │
│  Returns:                                                                   │
│    upload_id: UUID                                                          │
│    documents[]: { doc_id, filename, text_extracted, ocr_used,               │
│                   page_count, needs_client_ocr }                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: POST /api/v1/documents/extract                                     │
│                                                                             │
│  Input: { upload_id, documents[{ doc_id, text_extracted }], plan_context } │
│                                                                             │
│  ── PASS 1: Regex Extraction (extraction/regex_extractor.py) ──             │
│    Extracts deterministically:                                              │
│      • claim_reference_number     • plan_policy_number / group_number       │
│      • date_of_denial / service   • patient_member_id                       │
│      • treating_provider_npi      • icd10_diagnosis_codes (regex)           │
│      • cpt_procedure_codes        • hcpcs_codes + modifier_codes            │
│      • carc_codes / rarc_codes    • prior_auth_status / prior_auth_number   │
│      • currency_amounts           • financial_labeled dict                  │
│      • expedited_review_available • insurer_appeals_phone                   │
│      • state_commissioner_info_present                                      │
│    Multi-document: document_stitcher.py classifies each doc (denial/EOB/   │
│    bill) and applies authority rules to resolve conflicting fields.         │
│                                                                             │
│  ── PASS 2: LLM Extraction (extraction/llm_extractor.py) ──                 │
│    Groq/Gemini called with structured prompt on combined text.              │
│    Extracts contextual entities (Pass 1 struggles with these):              │
│      • patient_full_name            • treating_provider_name/specialty      │
│      • facility_name / address      • network_status                        │
│      • date_of_service/denial/eob   • denial_reason_narrative               │
│      • plan_provision_cited         • clinical_criteria_cited               │
│      • medical_necessity_statement  • procedure_description                 │
│      • billed / allowed / paid / denied amounts (with label context)        │
│      • internal/external appeal deadlines stated                            │
│      • insurer contact info                                                 │
│                                                                             │
│  Returns:                                                                   │
│    claim_object: ClaimObject (fully populated)                              │
│    extraction_confidence: { overall: 0.0–1.0, per_field: {...} }           │
│    warnings: string[]           (missing codes, no text, etc.)             │
│    document_types: { doc_id: "denial_letter"|"eob"|"medical_bill" }        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                              (parallel, non-blocking)
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2b (optional): POST /api/v1/wizard/plan-type                          │
│                                                                             │
│  Input: { source: employer|marketplace|medicaid|individual,                 │
│           employer_plan_type?: erisa|fully_insured|unknown,                 │
│           state: string }                                                   │
│                                                                             │
│  Logic:                                                                     │
│    Employer + ERISA    → ERISA federal routing                              │
│    Employer + Insured  → State DOI / ACA routing                            │
│    Marketplace         → State DOI / ACA routing                            │
│    Medicaid            → Medicaid fair hearing routing                      │
│    Individual          → State DOI / ACA routing                            │
│                                                                             │
│    Fetches live applicable_laws[] from eCFR via regulatory_fetch.py        │
│    Looks up state DOI from state_doi_contacts.json                          │
│                                                                             │
│  Returns: WizardResponse                                                    │
│    regulation_type, appeal_path[], primary_regulator, applicable_laws[],   │
│    state_specific (DOI name/phone/website/complaint_url)                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: POST /api/v1/claims/analyze                                        │
│                                                                             │
│  Input: { claim_object: ClaimObject, plan_context?: PlanContext }           │
│                                                                             │
│  Invokes: orchestrator.run_orchestrator()                                   │
│                                                                             │
│  ── Stage 0: Pre-classify root cause ──                                     │
│    analysis/root_cause_classifier.py → sets claim.derived.root_cause_category
│    (so regulation agent can use it for CMS coverage lookup)                 │
│                                                                             │
│  ── Stage 1: Three agents in parallel (asyncio.gather) ──                  │
│    ┌─────────────────────────────────────────────────────┐                  │
│    │  code_lookup_agent.py                               │                  │
│    │  ├── lookup_icd10()   → CMS/NLM ICD-10-CM API       │                  │
│    │  ├── lookup_cpt_hcpcs() → CMS/NLM HCPCS API         │                  │
│    │  ├── lookup_carc()    → Local CARC table (WPC)       │                  │
│    │  ├── lookup_rarc()    → Local RARC table (WPC)       │                  │
│    │  ├── lookup_npi()     → NPPES NPI Registry API       │                  │
│    │  └── web_search()     → Google fallback (unfound)    │                  │
│    └─────────────────────────────────────────────────────┘                  │
│    ┌─────────────────────────────────────────────────────┐                  │
│    │  regulation_agent.py                                │                  │
│    │  ERISA plans:                                       │                  │
│    │  ├── search_erisa()   → ERISA §503 lookup           │                  │
│    │  └── search_ecfr()    → 29 CFR 2560.503-1           │                  │
│    │  ACA/state plans:                                   │                  │
│    │  ├── search_aca_provisions() → ACA §2719            │                  │
│    │  └── search_ecfr()    → 45 CFR 147.136              │                  │
│    │  Medicaid:                                          │                  │
│    │  └── search_ecfr()    → 42 CFR 431.220              │                  │
│    │  Medical necessity (any):                           │                  │
│    │  └── search_cms_coverage() → CMS NCD database       │                  │
│    └─────────────────────────────────────────────────────┘                  │
│    ┌─────────────────────────────────────────────────────┐                  │
│    │  state_rules_agent.py                               │                  │
│    │  ├── search_idoi()    → Indiana DOI / 50-state DOI  │                  │
│    │  ├── get_doi_contact() → state_doi_contacts.json    │                  │
│    │  └── _determine_routing() → erisa_federal |          │                  │
│    │      state_doi | medicaid_state                     │                  │
│    └─────────────────────────────────────────────────────┘                  │
│                                                                             │
│  ── Stage 2: Analysis Agent (sequential, needs enrichment) ──               │
│    analysis_agent.py:                                                       │
│      1. classify_root_cause()       → LLM + heuristics → category+confidence
│      2. check_completeness()        → ACA/ERISA field checklist             │
│      3. triage_severity()           → urgent/time_sensitive/routine         │
│      4. calculate_deadlines()       → internal_appeal / external_review /   │
│                                       expedited  (with ICS events)          │
│      5. triage_severity() (final)   → refined with deadline proximity       │
│      6. estimate_probability()      → 0.0–1.0 approval probability          │
│      7. _build_assumptions()        → list of key assumptions made          │
│                                                                             │
│  Returns: OrchestratorResult                                                │
│    { claim_object, enrichment, analysis, sources[] }                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                        Frontend saves to sessionStorage
                        (claim_object, analysis, enrichment,
                         sources, plan_context, wizard)
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: Navigate to /action-plan                                           │
│                                                                             │
│  ActionPlan.tsx on mount fires 7 parallel output API calls                 │
│  (all cached in sessionStorage via outputsCache.ts):                       │
│                                                                             │
│    POST /api/v1/outputs/summary          → LLM plain-English summary        │
│    POST /api/v1/outputs/action-checklist → numbered steps with why-expanders│
│    POST /api/v1/outputs/completeness     → denial letter completeness check │
│    POST /api/v1/outputs/routing-card     → ERISA vs state DOI routing card  │
│    POST /api/v1/outputs/provider-brief   → one-page physician brief         │
│    POST /api/v1/outputs/deadlines        → deadline list + ICS data         │
│    (prefetch) POST /api/v1/outputs/appeal-letter  → 3-tab appeal package    │
│    (prefetch) POST /api/v1/outputs/assumptions    → assumptions panel       │
│                                                                             │
│  All calls go through output_agent.py → complete_llm() → Groq/Gemini       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5: User navigates to /appeal-drafting                                 │
│                                                                             │
│  AppealDrafting.tsx loads cached appeal letter (3 tabs):                   │
│    Tab 1: Appeal letter (formal letter citing regulations + clinical facts) │
│    Tab 2: Provider message (billing office request)                         │
│    Tab 3: Insurer message (member services contact)                         │
│                                                                             │
│  Export buttons:                                                            │
│    POST /api/v1/export/pdf  → fpdf2 PDF download                           │
│    POST /api/v1/export/ics  → .ics calendar file                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. API Reference — All Endpoints

### Health

| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| GET | `/api/v1/health` | — | Health check + version info |
| GET | `/health` | — | Same as above (for load balancers) |

### Documents

| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| POST | `/api/v1/documents/upload` | 10/min | Upload PDF/image files, extract text |
| POST | `/api/v1/documents/extract` | 10/min | Two-pass entity extraction → ClaimObject |

**Upload Request:** `multipart/form-data` with `files` field (up to 5 files, 10 MB each)
**Upload Response:**
```json
{
  "upload_id": "UUID",
  "documents": [{
    "doc_id": "UUID",
    "filename": "denial.pdf",
    "type": "pdf_digital|pdf_scanned|image",
    "text_extracted": "...",
    "ocr_used": false,
    "ocr_confidence": null,
    "page_count": 3,
    "needs_client_ocr": false
  }]
}
```

**Extract Request:**
```json
{
  "upload_id": "UUID",
  "documents": [{ "doc_id": "UUID", "text_extracted": "..." }],
  "plan_context": { "plan_type": "employer_erisa", "regulation_type": "erisa", "state": "IN" }
}
```

**Extract Response:**
```json
{
  "claim_object": { /* full ClaimObject */ },
  "extraction_confidence": { "overall": 0.82, "per_field": { "icd10_diagnosis_codes": 0.9, ... } },
  "warnings": ["No CPT codes found."],
  "document_types": { "doc-uuid": "denial_letter" }
}
```

### Wizard

| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| POST | `/api/v1/wizard/plan-type` | 20/min | Regulatory routing determination |

**Request:**
```json
{ "source": "employer", "employer_plan_type": "erisa", "state": "IN" }
```

**Response:**
```json
{
  "regulation_type": "erisa",
  "appeal_path": ["Step 1...", "Step 2..."],
  "primary_regulator": { "name": "DOL EBSA", "url": "...", "phone": "1-866-444-3272" },
  "applicable_laws": [{ "law": "ERISA §503", "section": "...", "url": "..." }],
  "state_specific": { "doi_name": "IDOI", "doi_phone": "...", "doi_website": "..." }
}
```

### Analysis

| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| POST | `/api/v1/claims/analyze` | 5/min | Full synchronous analysis (~8–16s) |
| POST | `/api/v1/claims/analyze/stream` | 5/min | SSE streaming analysis |

**Request (both):**
```json
{
  "claim_object": { /* ClaimObject */ },
  "plan_context": { "plan_type": "...", "regulation_type": "...", "state": "IN" }
}
```

**Response (synchronous):**
```json
{
  "enrichment": {
    "codes": { "M54.5": { "code_type": "icd10", "description": "...", "found": true } },
    "npi_details": { "1234567890": { "provider_name": "...", "specialty": "..." } },
    "regulations": {
      "regulation_type": "erisa",
      "applicable_laws": [{ "law": "ERISA", "section": "...", "url": "..." }],
      "appeal_process": ["Step 1..."],
      "internal_appeal_deadline_days": 180,
      "external_review_available": true,
      "coverage_determination": "..."
    },
    "state_rules": {
      "state": "IN",
      "doi_contact": { "name": "IDOI", "phone": "...", "website": "..." },
      "regulatory_routing": "state_doi",
      "routing_reason": "..."
    }
  },
  "analysis": {
    "root_cause": { "category": "prior_authorization", "confidence": 0.92, "responsible_party": "...", "reasoning": "..." },
    "denial_completeness": { "score": 0.75, "missing_fields": ["clinical_criteria"], "deficient": false, "escalation_available": true },
    "deadlines": {
      "internal_appeal": { "date": "YYYY-MM-DD", "days_remaining": 143, "source": "ACA §2719", "already_passed": false },
      "external_review": { "date": "YYYY-MM-DD", "days_remaining": 90, "source": "..." }
    },
    "approval_probability": { "score": 0.78, "reasoning": "...", "factors": [...] },
    "severity_triage": "time_sensitive",
    "assumptions": [{ "assumption": "...", "confidence": 0.85, "impact": "medium" }],
    "ics_events": [{ "title": "...", "date": "YYYY-MM-DD", "description": "..." }]
  },
  "sources": [{ "entity": "M54.5", "source_name": "CMS ICD-10-CM", "url": "..." }],
  "claim_object": { /* enriched ClaimObject */ }
}
```

**SSE Streaming Events (in order):**
```
event: started
data: { "message": "Analysis pipeline started", "upload_id": "..." }

event: codes_enriched
data: { "codes": { "M54.5": { "description": "...", "found": true } }, "code_count": 4 }

event: regulations_enriched
data: { "regulation_type": "erisa", "applicable_laws_count": 3, "internal_appeal_deadline_days": 180 }

event: state_rules_enriched
data: { "state": "IN", "regulatory_routing": "state_doi", "doi_name": "...", "doi_phone": "..." }

event: analysis_complete
data: { "root_cause": "prior_authorization", "severity_triage": "time_sensitive", "approval_probability": 0.78, "deadlines": {...} }

event: done
data: { "claim_object": {...}, "enrichment": {...}, "analysis": {...}, "sources": [...] }

event: error  (only on failure)
data: { "error": "..." }
```

### Codes

| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| GET | `/api/v1/codes/lookup?code=M54.5&type=icd10` | 30/min | Standalone code lookup |

Types: `icd10`, `cpt`, `hcpcs`, `carc`, `rarc`, `npi`

### Outputs (all POST, all accept `{ claim_object, analysis, enrichment }`)

| Path | Rate Limit | Returns | LLM? |
|------|-----------|---------|------|
| `/api/v1/outputs/summary` | default | `{ summary_text, reading_level, key_points[] }` | Yes |
| `/api/v1/outputs/action-checklist` | default | `{ steps[], total_steps }` | Yes |
| `/api/v1/outputs/appeal-letter` | default | `{ appeal_letter, provider_message, insurer_message, legal_citations[] }` | Yes |
| `/api/v1/outputs/provider-brief` | default | `{ brief_text, format, pdf_ready }` | Yes |
| `/api/v1/outputs/deadlines` | default | `{ deadlines[], reminders }` | No |
| `/api/v1/outputs/completeness` | default | `{ score, score_percentage, checklist[], deficient, escalation_available, ... }` | No |
| `/api/v1/outputs/routing-card` | default | `{ routing, primary_route, secondary_route, formatted_card }` | Yes |
| `/api/v1/outputs/assumptions` | default | `{ assumptions[], high_impact_count, overall_confidence, reliability_note }` | No |
| `/api/v1/outputs/probability` | default | `{ score, percentage, interpretation, reasoning, top_recommendation }` | No |

### Export

| Method | Path | Description | Returns |
|--------|------|-------------|---------|
| POST | `/api/v1/export/pdf` | Render markdown to PDF (fpdf2) | `application/pdf` binary |
| POST | `/api/v1/export/ics` | Generate .ics calendar event | `text/calendar` file |

**PDF Request:** `{ content: string, format: "appeal_letter"|"provider_brief"|"summary", title?: string }`
**ICS Request:** `{ event_title, event_date: "YYYY-MM-DD", description?, reminder_days_before?: [30, 7] }`

---

## 6. Agent Architecture & Interactions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATOR                                      │
│                         orchestrator.py                                     │
│                                                                             │
│  Input:  ClaimObject + PlanContext                                           │
│                                                                             │
│  Stage 0  ──────────────────────────────────────────────────────────────    │
│  ├── classify_root_cause(claim)  [analysis/root_cause_classifier.py]        │
│  └── Sets claim.derived.root_cause_category  (pre-classification)           │
│      WHY: regulation_agent needs root_cause to know if CMS                 │
│           coverage DB lookup is needed (medical_necessity only)             │
│                                                                             │
│  Stage 1 (asyncio.gather — all 3 run concurrently) ──────────────────────   │
│  ├── run_code_lookup_agent(claim)   ──→  CodeLookupResult                   │
│  │     All code lookups within agent also run in asyncio.gather             │
│  ├── run_regulation_agent(claim)    ──→  RegulationEnrichment               │
│  │     Regulation lookups within agent also run in asyncio.gather           │
│  └── run_state_rules_agent(claim)   ──→  StateRulesEnrichment               │
│                                                                             │
│  Stage 2 (sequential — needs Stage 1 data) ──────────────────────────────   │
│  └── run_analysis_agent(claim)      ──→  AnalysisResult                     │
│        ├── classify_root_cause()  (final, may refine pre-classification)    │
│        ├── check_completeness()                                             │
│        ├── triage_severity() (preliminary)                                  │
│        ├── calculate_deadlines()                                            │
│        ├── triage_severity() (final, with deadline proximity)               │
│        ├── estimate_probability()                                           │
│        └── _build_assumptions()                                             │
│                                                                             │
│  Assembles OrchestratorResult:                                              │
│    { claim_object, enrichment, analysis, sources[] }                        │
└─────────────────────────────────────────────────────────────────────────────┘

Agent Communication:
  - Agents do NOT call each other directly
  - All agents receive ClaimObject as input
  - Orchestrator merges their outputs into enrichment dict
  - ClaimObject.derived fields (root_cause_category, deadlines) are written
    by Analysis Agent and used downstream by Output Agent
```

### Agent: Code Lookup Agent

```
Input:  ClaimObject
Output: CodeLookupResult { codes: dict, npi_details: dict, sources: [], lookup_errors: [] }

For each code type found in ClaimObject, runs lookup in parallel:
  ICD-10 codes     → lookup_icd10()         → CMS/NLM API
  CPT codes        → lookup_cpt_hcpcs()     → CMS/NLM HCPCS API
  HCPCS codes      → lookup_cpt_hcpcs()     → CMS/NLM HCPCS API
  CARC codes       → lookup_carc()          → Local table (group+number parsing)
  RARC codes       → lookup_rarc()          → Local table
  NPI              → lookup_npi()           → NPPES Registry API

Post-processing:
  If any code not found → web_search() fallback via Google Custom Search
```

### Agent: Regulation Agent

```
Input:  ClaimObject (with erisa_or_state_regulated and root_cause_category)
Output: RegulationEnrichment

Dispatches based on regulation_type:
  ERISA            → search_erisa() + search_ecfr("29 CFR 2560.503-1")
  ACA/state/unknown → search_aca_provisions() + search_ecfr("45 CFR 147.136")
  Medicaid         → search_ecfr("42 CFR 431.220") + hardcoded Medicaid appeal steps

Always if root_cause == medical_necessity:
                   → search_cms_coverage() (CMS National Coverage Database)

Fills RegulationEnrichment:
  internal_appeal_deadline_days: 180 (ACA) or 60 (ERISA minimum)
  plan_review_deadline_days:     60
  expedited_turnaround_hours:    72
  external_review_available:     bool
  applicable_laws[]:             list of LegalCitation
  appeal_process[]:              ordered process steps
  required_notice_elements[]:   from ACA/ERISA
  coverage_determination:        CMS NCD summary (if medical_necessity)
```

### Agent: State Rules Agent

```
Input:  ClaimObject (state + regulation_type)
Output: StateRulesEnrichment

Steps:
  1. _determine_routing(regulation_type, state)
     ERISA     → "erisa_federal"   (DOL EBSA, not state DOI)
     Medicaid  → "medicaid_state"  (42 CFR §431.220 fair hearing)
     Other     → "state_doi"       (state Department of Insurance)

  2. search_idoi(state)  →  state DOI details
     Indiana: uses live IDOI API
     Other states: uses state_doi_contacts.json (static)

  Fills StateRulesEnrichment:
    doi_contact: { name, phone, address, complaint_url, website, ... }
    appeal_rules: (ERISA plans get DOL EBSA guidance instead)
    external_review_available / external_review_url
    consumer_resources
    regulatory_routing / routing_reason
```

### Agent: Analysis Agent

```
Input:  ClaimObject (post-Stage-1 enrichment)
Output: AnalysisResult

Sub-modules (all in analysis/):
  1. root_cause_classifier.py
     → RootCauseCategory: medical_necessity | prior_authorization |
       coding_billing_error | network_coverage |
       eligibility_enrollment | procedural_administrative
     → Uses LLM + heuristics; returns confidence score + responsible_party

  2. completeness_checker.py
     → Checks ACA §2719 / ERISA §503 required denial notice elements
     → Returns: score (0-1), missing_fields[], present_fields[],
       deficient (bool), escalation_available (bool)

  3. severity_triage.py
     → urgent:          deadline < 30 days OR life-sustaining treatment
     → time_sensitive:  deadline 30–60 days OR high denied amount
     → routine:         deadline > 60 days

  4. deadline_calculator.py
     → internal_appeal: denial_date + 180d (ACA) or 60d (ERISA min) or 90d (Medicaid)
     → external_review: denial_date + (ACA/state specific)
     → expedited:       available if urgent/life-threatening (72h turnaround)
     → Generates ICS event objects for calendar export

  5. probability_estimator.py
     → Base rate by root_cause category
     → Adjusted for: completeness score, regulation type, denial reason clarity
     → Returns: score (0-1), reasoning, factors[]

  6. _build_assumptions()
     → Explicit list of assumptions with confidence + impact + description
```

### Agent: Output Agent

```
Input:  claim_object dict + analysis dict (with embedded enrichment)
Output: Various LLM-generated content

All functions call complete_llm() from tools/llm_client.py (Groq → Gemini fallback)

generate_summary()           → plain-English denial explanation for patients
generate_action_checklist()  → numbered steps { number, action, detail, why }
generate_appeal_letter()     → { appeal_letter, provider_message, insurer_message, legal_citations[] }
generate_provider_brief()    → one-page summary for treating physician
generate_routing_card()      → ERISA vs DOI routing card with contact blocks
generate_completeness_report() → (deterministic, no LLM) field-by-field checklist
generate_assumptions_panel() → (deterministic, no LLM) structured assumptions
generate_probability_details() → (deterministic, no LLM) probability breakdown
```

---

## 7. Data Model: ClaimObject

The `ClaimObject` is the central data structure that flows through every stage of the pipeline. It is defined in `extraction/schema.py`.

```
ClaimObject
├── upload_id: str                   ← UUID assigned at upload time
├── source_documents: list[str]      ← list of doc_ids
│
├── identification: ClaimIdentification
│   ├── claim_reference_number
│   ├── date_of_service / date_of_denial / date_of_eob
│   ├── plan_policy_number / group_number
│   ├── plan_type: PlanType          ← employer_erisa | employer_fully_insured | marketplace | medicaid | individual
│   ├── plan_jurisdiction: str       ← "IN" (state abbreviation)
│   └── erisa_or_state_regulated: RegulationType  ← erisa | state | medicaid | unknown
│
├── patient_provider: PatientProviderEntities
│   ├── patient_full_name / patient_member_id / patient_dob
│   ├── treating_provider_name / treating_provider_npi / treating_provider_specialty
│   ├── facility_name / facility_address
│   └── network_status               ← "in-network" | "out-of-network"
│
├── service_billing: ServiceBillingEntities
│   ├── icd10_diagnosis_codes: list[str]
│   ├── cpt_procedure_codes: list[str]
│   ├── hcpcs_codes: list[str]
│   ├── modifier_codes: list[str]
│   ├── procedure_description
│   ├── place_of_service_code
│   └── units_of_service
│
├── financial: FinancialEntities
│   ├── billed_amount / allowed_amount / insurer_paid_amount / denied_amount
│   ├── patient_responsibility_total
│   ├── copay_amount / coinsurance_amount / deductible_applied
│   └── out_of_pocket_remaining
│
├── denial_reason: DenialReasonEntities
│   ├── carc_codes: list[str]        ← e.g. ["CO-197"]
│   ├── rarc_codes: list[str]
│   ├── denial_reason_narrative
│   ├── plan_provision_cited / clinical_criteria_cited / medical_necessity_statement
│   ├── prior_auth_status            ← "required_not_obtained" | "approved" | "denied"
│   └── prior_auth_number
│
├── appeal_rights: AppealRightsEntities
│   ├── internal_appeal_deadline_stated / external_review_deadline_stated
│   ├── expedited_review_available: bool
│   ├── insurer_appeals_contact_name / phone / address / fax
│   └── state_commissioner_info_present: bool
│
└── derived: DerivedEntities         ← Filled by Analysis Agent
    ├── root_cause_category: RootCauseCategory
    ├── responsible_party: str
    ├── denial_completeness_score: float (0-1)
    ├── appeal_deadline_internal / external / expedited: date
    ├── approval_probability_score: float (0-1)
    └── severity_triage: SeverityTriage  ← urgent | time_sensitive | routine
```

---

## 8. Extraction Pipeline (Phases 1 & 2)

### Phase 1 — Regex Extraction (`extraction/regex_extractor.py`)

Deterministic, instant, free. Extracts structured patterns:

| Category | Patterns Used |
|----------|--------------|
| Claim IDs | `CLM\d+`, `CLAIM-\d+`, claim reference patterns |
| Dates | ISO dates (`YYYY-MM-DD`), US formats (`MM/DD/YYYY`) |
| Policy/Group # | Policy, group, member ID patterns |
| ICD-10 | `[A-Z]\d{2}\.?\d+` |
| CPT | 5-digit codes (contextual) |
| HCPCS | `[A-V]\d{4}` |
| CARC | `CO-\d+`, `PR-\d+`, `OA-\d+`, `PI-\d+` |
| RARC | `N\d+`, `M\d+` |
| NPI | 10-digit number preceded by "NPI" |
| Currency | `\$[\d,]+\.?\d*` (labeled and positional) |
| Prior Auth | "prior authorization", "auth number" patterns |
| Phone | `\(\d{3}\)\s?\d{3}-\d{4}` |

### Phase 2 — LLM Extraction (`extraction/llm_extractor.py`)

LLM prompt sent to Groq/Gemini with combined document text + Pass 1 results as context. Structured JSON output requested. Extracts:

- Natural-language entities: names, addresses, narratives
- Contextual financial amounts (labeled correctly, not positional)
- Appeal deadlines stated in the document
- Insurer contact info, clinical criteria, procedure descriptions

**Confidence Scoring:**
- `0.7` — regex found it
- `0.9` — LLM found it
- `1.0` — both agree

### Multi-Document Stitching (`extraction/document_stitcher.py`)

When multiple documents are provided:
1. Each document is classified (`classify_document()`): denial_letter | eob | medical_bill | unknown
2. Authority rules applied:
   - Denial letter → authoritative for: claim IDs, appeal rights, denial reason
   - EOB → authoritative for: codes, financial amounts, dates of service
   - Medical bill → authoritative for: facility details, itemized charges
3. Conflicting values resolved by source authority
4. Warnings generated for unresolvable conflicts

---

## 9. Orchestrator & Parallel Agent Execution

```python
# Simplified orchestration logic

# Stage 0: Pre-classify root cause FIRST
root_cause_pre = await classify_root_cause(claim)
claim.derived.root_cause_category = root_cause_pre.category
# This is critical: regulation_agent uses root_cause to decide if
# CMS coverage lookup is needed (only for medical_necessity)

# Stage 1: All 3 agents in parallel
code_result, regulation_result, state_result = await asyncio.gather(
    run_code_lookup_agent(claim),
    run_regulation_agent(claim),
    run_state_rules_agent(claim),
)

# Stage 2: Analysis (sequential, needs full claim data)
analysis_result = await run_analysis_agent(claim)

# Assemble final response
return OrchestratorResult(
    claim_object=claim.model_dump(),
    enrichment=_build_enrichment_dict(code_result, regulation_result, state_result),
    analysis=analysis_result.model_dump(),
    sources=_collect_sources(...)
)
```

**Streaming Mode (SSE):**
Same stages, but each completion yields an SSE event. The frontend can start rendering partial results as soon as `codes_enriched` arrives, without waiting for the full pipeline.

**Error isolation:** Each parallel task uses `return_exceptions=False`; if one agent fails, the orchestrator raises immediately. Individual code lookups within the Code Lookup Agent use `return_exceptions=True` so one bad code doesn't block others.

---

## 10. Analysis Modules

### Root Cause Classification (`analysis/root_cause_classifier.py`)

**Categories:**
- `medical_necessity` — coverage denied for lack of medical necessity
- `prior_authorization` — pre-approval not obtained (CARC CO-197 is a strong signal)
- `coding_billing_error` — incorrect codes, upcoding, unbundling
- `network_coverage` — out-of-network provider
- `eligibility_enrollment` — not covered under the plan at time of service
- `procedural_administrative` — filing deadline missed, wrong insurer, etc.

**Classification Method:** Heuristic rule engine first (CARC/denial narrative keyword matching). If confidence < 0.75, calls LLM for disambiguation. Returns category + confidence + responsible_party + reasoning + classification_method.

### Deadline Calculator (`analysis/deadline_calculator.py`)

| Regulation Type | Internal Appeal | External Review | Expedited |
|----------------|----------------|-----------------|-----------|
| ERISA (minimum) | 60 days | N/A | 72h (urgent) |
| ACA / state | 180 days | 4 months | 72h (urgent) |
| Medicaid | 90 days | N/A (fair hearing) | — |

Dates calculated from `date_of_denial`. Generates `ICS event objects` for calendar export with 14-day-before reminders.

### Completeness Checker (`analysis/completeness_checker.py`)

Checks denial notice against ACA §2719 / ERISA §503 required elements:
- Specific denial reason with reference to plan provision
- Clinical criteria used (if applicable)
- Date of denial + claim reference
- Internal appeal deadline stated
- External review notice (if applicable)
- Insurer contact information
- State commissioner info (for state-regulated plans)

Returns score (0–1), missing/present field lists, `deficient` flag, `escalation_available` (deficient denial can be challenged independently).

### Probability Estimator (`analysis/probability_estimator.py`)

Base rates by root cause:
- Prior auth (retroactive): ~70–80%
- Coding error: ~65–75%
- Medical necessity: ~55–70%
- Network (gap exception): ~40–55%
- Eligibility: ~20–35%

Modifiers: completeness score, regulation type (ERISA harder), denial narrative clarity, denial amount significance.

---

## 11. Output Generation

All LLM-generated outputs flow through `agents/output_agent.py` → `tools/llm_client.py`.

### LLM Client (`tools/llm_client.py`)

```
complete_llm(prompt)
  ├── Try Groq (llama-3.3-70b-versatile)
  │     Rate limit: max 1 concurrent request, 2s min delay between calls
  │     Retry on 429 with exponential backoff
  ├── Fallback: Groq (llama-3.1-8b-instant)
  ├── Fallback: Gemini 2.5 Flash
  ├── Fallback: Gemini 2.5 Flash Lite
  └── Fallback: Ollama llama3.2 (dev only, ollama_enabled=False by default)
```

JSON responses use `_repair_truncated_json()` to handle truncated LLM outputs (closes unclosed braces/strings).

### Summary Output

Generated by LLM. Prompt includes: patient name, provider, denied amount, denial reason narrative, CARC codes (with plain-English from Code Lookup Agent), applicable regulations. Returns: `summary_text` (patient reading level), `reading_level`, `key_points[]`.

### Action Checklist Output

Generated by LLM. Each step: `number`, `action` (title), `detail` (what to do), `why` (legal/regulatory reason). Typically 4–7 steps ordered by priority.

### Appeal Letter Output

Generated by LLM. Returns three documents:
1. `appeal_letter` — formal letter to insurer citing specific regulations, clinical facts, code meanings
2. `provider_message` — message to provider's billing office requesting retroactive auth / corrected codes
3. `insurer_message` — message to insurer's member services

### Provider Brief Output

One-page summary formatted for the treating physician. Includes denial context, what is being requested of the provider, supporting evidence needed.

### Routing Card Output

LLM-generated ERISA vs. state DOI routing card with:
- `primary_route` — the correct regulatory path
- `secondary_route` — alternative path (e.g., DOL EBSA if ERISA but insurer is state-licensed)
- `formatted_card` — patient-readable routing summary

---

## 12. Frontend Architecture

```
frontend/src/
├── main.tsx                     ← React app entry point (Vite)
├── App.tsx                      ← BrowserRouter + route definitions
│
├── pages/
│   ├── LandingPage.tsx          ← / — hero, feature overview
│   ├── AnalyzeFlow.tsx          ← /analyze — Upload wizard + pipeline execution
│   ├── ActionPlan.tsx           ← /action-plan — Main results dashboard
│   ├── AppealDrafting.tsx       ← /appeal-drafting — Appeal letter 3-tab view
│   ├── BillBreakdown.tsx        ← /bill-breakdown — Itemized bill analysis
│   ├── ResultsDashboard.tsx     ← (legacy demo dashboard, not in routing)
│   ├── IndianaResourcesLayout.tsx ← /indiana-resources layout wrapper
│   ├── IndianaResourcesHub.tsx  ← /indiana-resources (IDOI resources)
│   └── CodeLookupContent.tsx   ← /code-lookup (standalone code search)
│
├── components/
│   ├── Navbar.tsx
│   └── Footer.tsx
│
└── lib/
    ├── api.ts                   ← All fetch wrappers for backend API
    ├── outputsCache.ts          ← sessionStorage cache layer for LLM outputs
    ├── sessionKeys.ts           ← Session key constants + save/load helpers
    ├── planMapping.ts           ← Maps UI selections to PlanContext/WizardBody
    ├── billBreakdownFromBundle.ts ← Extracts bill data from analysis bundle
    ├── parseMoney.ts            ← Currency parsing utilities
    └── sessionKeys.ts           ← Storage key constants
```

---

## 13. Frontend Session Storage & Caching

### Analysis Bundle (persisted after /claims/analyze completes)

| Key | Content |
|-----|---------|
| `resolvly_analysis_complete` | `"1"` flag |
| `resolvly_claim_object` | Full ClaimObject JSON |
| `resolvly_analysis` | AnalysisResult JSON |
| `resolvly_enrichment` | Enrichment dict JSON |
| `resolvly_sources` | Sources array JSON |
| `resolvly_plan_context` | PlanContext JSON |
| `resolvly_wizard` | WizardResponse JSON |
| `resolvly_doc_profile` | `{ files[], kindsPresent: {eob, denial, medical_bill} }` |

### Outputs Cache (`outputsCache.ts`)

All LLM output API calls are wrapped in a cache layer. Cache is keyed by `analysisBundleFingerprint` (a hash of claim_object + analysis + enrichment). Cache is automatically invalidated when a new analysis is run.

```
resolvly_output_cache_summary
resolvly_output_cache_action_checklist
resolvly_output_cache_appeal_letter_{patientInfoJSON}
resolvly_output_cache_provider_brief
resolvly_output_cache_deadlines
resolvly_output_cache_assumptions
resolvly_output_cache_routing_card
resolvly_output_cache_completeness
resolvly_output_cache_probability
```

**Prefetching:** `ActionPlan.tsx` prefetches `appeal_letter` and `assumptions` in background so `/appeal-drafting` opens instantly without a loading state.

---

## 14. Frontend Routes & Pages

### `/` — LandingPage

Marketing page. CTA leads to `/analyze`.

### `/analyze` — AnalyzeFlow (Upload & Context Wizard)

Two-column layout:
- **Left:** Policy Intelligence (plan type + funding structure selection)
- **Right:** Three document upload slots (Denial Letter, EOB, Medical Bill)

Requirements to enable "Begin Forensic Analysis":
- All 3 document slots filled
- Plan type selected (employer / individual / medicaid)
- Funding structure selected (ERISA / Fully Insured) if employer

On submit → `setPhase('processing')` → animated pipeline UI while `runPipeline()` executes:
1. `uploadDocuments(files)` → `/documents/upload`
2. `extractEntities({upload_id, documents, plan_context})` → `/documents/extract`
3. `wizardPlanType(body)` → `/wizard/plan-type` (non-blocking failure)
4. `analyzeClaim(claim_object, plan_context)` → `/claims/analyze`
5. `saveAnalysisBundle(bundle)` → sessionStorage
6. `navigate('/action-plan')`

### `/action-plan` — ActionPlan (Main Results Dashboard)

Loads analysis bundle from sessionStorage. On mount fires 8 API calls (all via outputsCache):
- Summary, Action Checklist, Completeness, Routing Card, Provider Brief, Deadlines → rendered on page
- Appeal Letter, Assumptions → prefetched in background

**Layout:**
- Header: severity badge + circular approval probability gauge
- Left column (8/12): Denial summary, Recovery Roadmap (steps), Denial Notice Completeness table
- Right column (4/12): Critical Deadlines (with .ics download), Provider Brief, Bill Breakdown, Regulatory Routing card

### `/appeal-drafting` — AppealDrafting

Three tabs: Appeal Letter | Provider Message | Insurer Message
Loaded from outputsCache (prefetched by ActionPlan).
Export buttons: PDF download, copy to clipboard.

### `/bill-breakdown` — BillBreakdown

Itemized financial analysis from analysis bundle. Parses financial entities from ClaimObject.

### `/indiana-resources` — IndianaResourcesHub

Static + live IDOI resources, regulatory guides, consumer assistance links.

### `/code-lookup` — CodeLookupContent

Interactive code lookup using `GET /api/v1/codes/lookup`. Supports all 6 code types.

---

## 15. LLM Configuration & Fallback Chain

```
Settings (config.py):
  groq_api_key
  groq_model_primary:   "llama-3.3-70b-versatile"
  groq_model_fallback:  "llama-3.1-8b-instant"
  gemini_api_key
  gemini_model_primary: "gemini-2.5-flash"
  gemini_model_fallback:"gemini-2.5-flash-lite"
  ollama_enabled:       False
  ollama_model:         "llama3.2"

Rate limiting:
  llm_max_concurrent_requests: 1
  llm_min_delay_between_requests: 2.0s
  llm_retry_on_rate_limit: True (exponential backoff on 429)
```

**Fallback order in complete_llm():**
1. Groq primary (llama-3.3-70b-versatile)
2. Groq fallback (llama-3.1-8b-instant)
3. Gemini primary (gemini-2.5-flash)
4. Gemini fallback (gemini-2.5-flash-lite)
5. Ollama (dev only, disabled by default)

---

## 16. External Tool Integrations

| Tool | File | API | Used For |
|------|------|-----|---------|
| CMS ICD-10-CM | `tools/cms_icd_lookup.py` | NLM/CMS REST API | ICD-10 diagnosis code lookup |
| CMS HCPCS | `tools/cms_hcpcs_lookup.py` | CMS/NLM HCPCS API | CPT + HCPCS procedure code lookup |
| CARC/RARC | `tools/carc_rarc_lookup.py` | Local table (WPC source) | Denial reason code lookup |
| NPPES NPI | `tools/npi_registry.py` | NPPES REST API | Provider name, specialty, address |
| eCFR | `tools/ecfr_search.py` | eCFR.gov API | Federal regulation text lookup |
| ERISA | `tools/erisa_search.py` | Custom (eCFR + DOL) | ERISA §503 appeal rules |
| ACA | `tools/aca_search.py` | Custom (eCFR) | ACA §2719 internal/external review rules |
| CMS Coverage DB | `tools/cms_coverage.py` | CMS NCD/LCD API | National Coverage Determinations |
| Indiana DOI | `tools/idoi_search.py` | IDOI + 50-state JSON | State DOI contact + appeal resources |
| State DOI JSON | `tools/state_doi_lookup.py` | `data/state_doi_contacts.json` | All 50 state DOI contacts (static) |
| Regulatory Fetch | `tools/regulatory_fetch.py` | eCFR API | Live law citations for wizard |
| Google Search | `tools/web_search.py` | Google Custom Search API | Fallback for unfound codes |

---

## 17. Export Pipeline

### PDF Export (`/api/v1/export/pdf`)

1. Receives markdown string + format type
2. `_markdown_to_plain_lines()` parses markdown into `(style, text)` pairs
3. `_generate_pdf()` renders using fpdf2:
   - H1/H2/H3 headings → Helvetica Bold at different sizes
   - Body text → word-wrapped multi_cell
   - Bullet points → Unicode bullet prefix
   - Horizontal rules → drawn line
4. Returns `application/pdf` binary with `Content-Disposition: attachment`

### ICS Export (`/api/v1/export/ics`)

1. Receives event_title, event_date (ISO), description, reminder_days_before[]
2. `_build_ics()` generates RFC 5545-compliant iCalendar string
3. Multiple VALARM blocks for each reminder day
4. Returns `text/calendar` with filename based on sanitized event title

Frontend handles ICS in two ways:
- If `ics_data` is already in the deadlines response → creates Blob directly (no extra API call)
- Otherwise → calls `POST /api/v1/export/ics` for fresh generation

---

## 18. Rate Limiting & Security

```
FastAPI app with SlowAPI middleware:
  - /documents/upload:      10 requests/minute
  - /documents/extract:     10 requests/minute
  - /claims/analyze:         5 requests/minute
  - /claims/analyze/stream:  5 requests/minute
  - /wizard/plan-type:      20 requests/minute
  - /codes/lookup:          30 requests/minute

CORS:
  allowed_origins: ["http://localhost:3000", "https://*.vercel.app"]
  allow_methods:   ["GET", "POST"]
  allow_headers:   ["Content-Type", "Accept"]
  allow_credentials: False

File validation:
  max_file_size:   10 MB per file
  max_files:       5 files per request
  allowed_types:   application/pdf, image/jpeg, image/png, image/webp, image/tiff
```

---

## 19. Key Architectural Decisions

### 1. Fully Stateless Design
No database, no sessions, no user accounts. All state flows through `sessionStorage` in the browser. Trade-off: can't persist results across browser sessions, but zero infrastructure complexity.

### 2. Pre-classification Before Parallel Agents
Root cause is classified **before** parallel agents start (Stage 0). This is critical because `regulation_agent` needs `root_cause_category` to know whether to query the CMS Coverage Database (only for `medical_necessity` denials).

### 3. Two-Pass Extraction
Regex (Pass 1) is free, fast, and always runs. LLM (Pass 2) handles contextual entities that regex can't reliably extract. The two passes are complementary — confidence is highest when both agree.

### 4. LLM Fallback Chain
Multiple LLM providers with automatic fallback prevents single-provider rate limits from breaking the pipeline. The chain progresses from most capable to most available: Groq 70B → Groq 8B → Gemini Flash → Gemini Flash Lite → Ollama (local, dev only).

### 5. Frontend Output Caching
All LLM-generated outputs are cached in `sessionStorage` keyed by analysis bundle fingerprint. This prevents re-calling expensive LLM APIs when the user navigates between pages. Cache is automatically invalidated when a new document is uploaded.

### 6. Appeal Letter Prefetching
`ActionPlan.tsx` prefetches the appeal letter in the background (fire-and-forget `void` call). This makes `/appeal-drafting` open instantly without a loading state, since the LLM call takes 3–8 seconds.

### 7. ERISA vs. State DOI Routing
The `state_rules_agent` always fetches DOI contact info, even for ERISA plans. For ERISA plans, the DOI contact is included with a note that "state DOI doesn't regulate self-funded plans" but the DOL EBSA does. This is intentional — state attorneys general sometimes have concurrent jurisdiction.

### 8. No Local Knowledge Base for Codes
CARC/RARC are the only codes stored locally (no public API exists). All other codes (ICD-10, CPT, HCPCS, NPI) are looked up live against authoritative public APIs. This ensures up-to-date definitions and avoids licensing issues with AMA CPT codes.

### 9. Multi-Document Stitching
Document stitching resolves conflicts between documents using authority rules (denial letter wins for claim ID and appeal rights; EOB wins for codes and financials). This is key for accurate extraction when information is spread across multiple documents.

### 10. Streaming vs. Synchronous Analysis
Both `/claims/analyze` (synchronous) and `/claims/analyze/stream` (SSE) are implemented. The frontend currently uses the synchronous endpoint. The streaming endpoint exists for future progressive rendering enhancement.
