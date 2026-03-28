# Insurance Claim & Billing Debugger — Implementation Plan

> **Version:** 1.0
> **Author:** Principal AI/Data Engineering Team
> **Date:** March 2026
> **Status:** Technical Blueprint — Ready for Development

---

## Table of Contents

1. [Project Summary](#1-project-summary)
2. [User Input Documents](#2-user-input-documents)
3. [Entity Extraction Schema](#3-entity-extraction-schema)
4. [Document Processing Pipeline](#4-document-processing-pipeline)
5. [Multi-Agent Architecture](#5-multi-agent-architecture)
6. [API Design](#6-api-design)
7. [Feature-to-API Mapping](#7-feature-to-api-mapping)
8. [End-to-End Flow Orchestration](#8-end-to-end-flow-orchestration)
9. [Frontend Architecture](#9-frontend-architecture)
10. [Infrastructure & Free-Tier Hosting Strategy](#10-infrastructure--free-tier-hosting-strategy)
11. [Repository Structure](#11-repository-structure)
12. [Development Phases & Sprint Plan](#12-development-phases--sprint-plan)
13. [Security, Privacy & Compliance Notes](#13-security-privacy--compliance-notes)

---

## 1. Project Summary

### What We Build

An AI-powered web application that takes a patient's insurance denial letter, EOB, or hospital bill and:

1. Extracts every code, date, amount, and entity from the document
2. Sends an AI agent to look up each code/regulation from **verified government and regulatory sources in real time** (no local knowledge base)
3. Classifies the root cause of denial into one of 6 categories
4. Explains everything in plain English
5. Generates an action plan, appeal letters, deadline tracking, and provider communication briefs

### Key Architectural Decision: Live Lookup Over Local KB

We do **NOT** build or maintain a local database of billing codes, regulations, or insurer policies. Instead, a **multi-agent system with tool access** fetches authoritative data on the fly from:

| Source Domain | Endpoints / Sources |
|---|---|
| Federal billing codes (CPT, ICD-10, HCPCS) | CMS.gov HCPCS lookup, WHO ICD API, AMA CPT API (free tier) |
| CARC / RARC denial codes | X12 Washington Publishing Company (WPC) public tables, CMS remittance advice docs |
| Federal regulations (ACA, ERISA) | HHS.gov, DOL.gov ERISA advisory opinions, eCFR.gov |
| State-level rules (Indiana-first) | Indiana DOI (IDOI) website, IN.gov insurance consumer resources |
| Medicare / Medicaid coverage | CMS LCD/NCD database, Medicare Coverage Database API |
| Clinical guidelines (public) | CMS National Coverage Determinations, AHRQ clinical guidelines |

This means: zero maintenance cost for code tables, always-current regulatory data, and a much lighter infrastructure footprint.

---

## 2. User Input Documents

The system needs documents from the user to begin analysis. Here is every document type we accept, what it contains, and why we need it.

### 2.1 Primary Documents (At Least One Required)

#### A. Insurance Denial Letter (Adverse Benefit Determination Notice)

- **What it is:** The formal letter from the insurer stating a claim has been denied
- **Format:** PDF, scanned image (JPG/PNG), photo, screenshot
- **Why we need it:** Contains the denial reason, CARC/RARC codes, appeal rights, deadlines, and insurer contact information
- **Critical data inside:**
  - Denial reason code(s) and narrative
  - Claim/reference number
  - Date of denial
  - Service description and dates
  - Appeal instructions and deadlines
  - Insurer contact info
  - Plan provision / policy clause cited

#### B. Explanation of Benefits (EOB)

- **What it is:** The document the insurer sends after processing a claim showing what was billed, what they paid, and what the patient owes
- **Format:** PDF, scanned image, photo, screenshot
- **Why we need it:** Shows the full financial breakdown — billed amount, allowed amount, insurer payment, adjustments, and patient responsibility — plus adjustment reason codes
- **Critical data inside:**
  - Provider name and NPI
  - ICD-10 diagnosis codes
  - CPT/HCPCS procedure codes
  - Billed amount, allowed amount, paid amount
  - Patient responsibility (copay, coinsurance, deductible)
  - Adjustment reason codes (CARC) and remark codes (RARC)
  - Claim number and date of service

#### C. Hospital / Provider Bill (Medical Bill / Statement)

- **What it is:** The bill sent directly from the hospital or doctor's office
- **Format:** PDF, scanned image, photo, screenshot
- **Why we need it:** Sometimes patients receive a bill without ever seeing the denial letter or EOB. This gives us procedure codes, billed amounts, and provider info to start the investigation
- **Critical data inside:**
  - Itemised charges with CPT/HCPCS codes
  - Total billed amount and balance due
  - Provider name, address, and billing contact
  - Date(s) of service
  - Patient account number

### 2.2 Supporting Documents (Optional but Valuable)

| Document | Why It Helps |
|---|---|
| Insurance card (photo) | Extracts plan type, group number, member ID, insurer name, and network tier — feeding the Plan Type Wizard |
| Prior authorization letter | If available, proves auth was granted — directly counters "missing prior auth" denials |
| Referral letter | Proves a referral was obtained — counters referral-based denials |
| Doctor's letter of medical necessity | Strengthens appeal; if already written, we incorporate it into the appeal letter |
| Previous appeal submission(s) | If the user has already appealed and been denied again, we tailor the next-level appeal strategy |

### 2.3 Upload Formats Supported

| Format | Method | Processing |
|---|---|---|
| PDF (digital) | File upload | Direct text extraction via `pdf-parse` / `pdfplumber` |
| PDF (scanned) | File upload | OCR via Tesseract.js (local) or Google Vision API (free tier) |
| Image (JPG/PNG) | File upload or camera capture | OCR via Tesseract.js or Google Vision API |
| Screenshot | Drag-and-drop, paste from clipboard | OCR with auto-crop detection |
| Mobile photo | Camera capture via `<input capture>` | OCR with perspective correction preprocessing |

### 2.4 Multi-Document Stitching

When a user uploads multiple documents (e.g., an EOB + a denial letter for the same visit), the system stitches them into a single unified claim record by matching on:

- Provider name (fuzzy match)
- Date of service (exact or ±1 day)
- Procedure codes (exact match)
- Claim/reference number (if present on both)

This creates a single **Claim Object** with a consolidated timeline.

---

## 3. Entity Extraction Schema

Every document is parsed into a structured **Claim Object**. Below is the complete entity schema — every field the system extracts or derives.

### 3.1 Claim Identification Entities

| Entity | Source Document(s) | Extraction Method | Required |
|---|---|---|---|
| `claim_reference_number` | Denial letter, EOB | Regex pattern + NLP | Yes |
| `date_of_service` | All | Date parser (multiple formats) | Yes |
| `date_of_denial` | Denial letter | Date parser | Yes |
| `date_of_eob` | EOB | Date parser | If EOB uploaded |
| `plan_policy_number` | Denial letter, insurance card | Regex + OCR | Yes |
| `group_number` | Denial letter, insurance card | Regex | If employer plan |
| `plan_type` | Derived from Plan Type Wizard or insurance card | User input + OCR | Yes |
| `plan_jurisdiction` | Derived from state + plan type | Rules engine | Yes |
| `erisa_or_state_regulated` | Derived from plan type | Rules engine | Yes |

### 3.2 Patient & Provider Entities

| Entity | Source Document(s) | Extraction Method | Required |
|---|---|---|---|
| `patient_full_name` | All | NER (Named Entity Recognition) | Yes |
| `patient_member_id` | Denial letter, EOB, insurance card | Regex | Yes |
| `patient_dob` | EOB, insurance card | Date parser | If available |
| `treating_provider_name` | All | NER | Yes |
| `treating_provider_npi` | EOB, denial letter | Regex (10-digit NPI) | Yes |
| `treating_provider_specialty` | EOB | NLP extraction | If available |
| `facility_name` | Hospital bill, EOB | NER | If available |
| `facility_address` | Hospital bill | Address parser | If available |
| `network_status` | EOB, denial letter | NLP keyword extraction | If available |

### 3.3 Service & Billing Code Entities

| Entity | Source Document(s) | Extraction Method | Required |
|---|---|---|---|
| `icd10_diagnosis_codes[]` | EOB, denial letter | Regex (`[A-Z][0-9]{2}\.[0-9]{1,4}`) | Yes |
| `cpt_procedure_codes[]` | EOB, hospital bill | Regex (5-digit numeric) | Yes |
| `hcpcs_codes[]` | EOB | Regex (`[A-Z][0-9]{4}`) | If present |
| `procedure_description` | All | NLP extraction | Yes |
| `service_date_range` | All | Date range parser | If multi-day service |
| `place_of_service_code` | EOB | Regex (2-digit) | If present |
| `units_of_service` | EOB, hospital bill | Numeric extraction | If present |
| `modifier_codes[]` | EOB | Regex (2-char alpha/numeric) | If present |

### 3.4 Financial Entities

| Entity | Source Document(s) | Extraction Method | Required |
|---|---|---|---|
| `billed_amount` | All | Currency parser | Yes |
| `allowed_amount` | EOB | Currency parser | If EOB present |
| `insurer_paid_amount` | EOB | Currency parser | If EOB present |
| `denied_amount` | Denial letter, EOB | Currency parser / derived | Yes |
| `patient_responsibility_total` | EOB, hospital bill | Currency parser | Yes |
| `copay_amount` | EOB | Currency parser | If applicable |
| `coinsurance_amount` | EOB | Currency parser | If applicable |
| `deductible_applied` | EOB | Currency parser | If applicable |
| `out_of_pocket_remaining` | EOB | Currency parser | If present |

### 3.5 Denial Reason Entities

| Entity | Source Document(s) | Extraction Method | Required |
|---|---|---|---|
| `carc_codes[]` | Denial letter, EOB | Regex + lookup | Yes |
| `rarc_codes[]` | EOB | Regex + lookup | If present |
| `denial_reason_narrative` | Denial letter | NLP full-text extraction | Yes |
| `plan_provision_cited` | Denial letter | NLP extraction | If present |
| `clinical_criteria_cited` | Denial letter | NLP extraction | If present |
| `medical_necessity_statement` | Denial letter | NLP extraction | If present |
| `prior_auth_status` | Denial letter | NLP keyword classification | Yes |
| `prior_auth_number` | Denial letter, prior auth letter | Regex | If present |

### 3.6 Appeal Rights & Contact Entities

| Entity | Source Document(s) | Extraction Method | Required |
|---|---|---|---|
| `internal_appeal_deadline_stated` | Denial letter | Date parser / NLP | Yes |
| `external_review_deadline_stated` | Denial letter | Date parser / NLP | If present |
| `expedited_review_available` | Denial letter | NLP boolean extraction | Yes |
| `insurer_appeals_contact_name` | Denial letter | NER | Yes |
| `insurer_appeals_phone` | Denial letter | Phone regex | Yes |
| `insurer_appeals_address` | Denial letter | Address parser | Yes |
| `insurer_appeals_fax` | Denial letter | Phone regex | If present |
| `state_commissioner_info_present` | Denial letter | NLP boolean | For completeness check |

### 3.7 Derived / Computed Entities (Not Extracted — Calculated)

| Entity | How It's Derived |
|---|---|
| `root_cause_category` | AI classifier (1 of 6 categories) |
| `responsible_party` | Rules engine + AI reasoning |
| `denial_completeness_score` | Checklist of ACA/state required fields vs. what's present |
| `appeal_deadline_internal` | `date_of_denial` + 180 days (ACA) or 60 days (ERISA) |
| `appeal_deadline_external` | `date_of_denial` + 4 months (ACA) or state-specific |
| `appeal_deadline_expedited` | If urgent: 72 hours from filing |
| `approval_probability_score` | ML model / rules engine based on cause category + code + jurisdiction |
| `severity_triage` | Rules engine: Urgent / Time-Sensitive / Routine |

---

## 4. Document Processing Pipeline

### 4.1 Pipeline Overview

```
User Upload
    │
    ▼
┌────────────────────────────┐
│  STAGE 1: INGESTION        │
│  ┌──────────────────────┐  │
│  │ File type detection   │  │
│  │ PDF → text extraction │  │
│  │ Image → OCR           │  │
│  │ Multi-doc grouping    │  │
│  └──────────────────────┘  │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│  STAGE 2: ENTITY EXTRACT   │
│  ┌──────────────────────┐  │
│  │ LLM-powered parsing   │  │
│  │ Regex code extraction │  │
│  │ NER for names/orgs    │  │
│  │ Currency/date parsing │  │
│  │ Schema validation     │  │
│  └──────────────────────┘  │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│  STAGE 3: ENRICHMENT       │
│  (Multi-Agent Live Lookup) │
│  ┌──────────────────────┐  │
│  │ Code Lookup Agent     │  │
│  │ Regulation Agent      │  │
│  │ State Rules Agent     │  │
│  │ Coverage Agent        │  │
│  └──────────────────────┘  │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│  STAGE 4: ANALYSIS         │
│  ┌──────────────────────┐  │
│  │ Root cause classifier │  │
│  │ Responsibility attr.  │  │
│  │ Completeness checker  │  │
│  │ Deadline calculator   │  │
│  │ Probability estimator │  │
│  └──────────────────────┘  │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│  STAGE 5: OUTPUT GEN       │
│  ┌──────────────────────┐  │
│  │ Plain-English summary │  │
│  │ Action checklist      │  │
│  │ Appeal letter drafts  │  │
│  │ Provider brief        │  │
│  │ Timeline + deadlines  │  │
│  └──────────────────────┘  │
└────────────┴───────────────┘
             │
             ▼
        Frontend UI
```

### 4.2 Stage 1: Ingestion — Technology Stack

```
Input Handling:
├── PDF (digital text)
│   └── pdf-parse (Node.js) or PyMuPDF/pdfplumber (Python)
│       → Extract raw text preserving layout
│
├── PDF (scanned / image-only)
│   └── Tesseract.js (client-side, free, no API key)
│       OR Google Cloud Vision API (300 free units/month)
│       → OCR to text
│
├── Image upload (JPG/PNG)
│   └── Pre-processing: auto-rotate, deskew, contrast enhance
│       → Tesseract.js or Google Vision API → text
│
├── Screenshot / clipboard paste
│   └── Canvas API crop UI → same OCR pipeline
│
└── Mobile camera capture
    └── HTML <input type="file" accept="image/*" capture="environment">
        → client-side resize/compress → OCR pipeline
```

**Why Tesseract.js as primary OCR:** Free, runs in-browser (no server cost), good accuracy for printed text. Google Vision API is the fallback for low-quality scans (300 req/month free).

### 4.3 Stage 2: Entity Extraction — Hybrid Approach

We use a **two-pass extraction strategy:**

**Pass 1 — Deterministic Extraction (Regex + Rules)**

Fast, free, runs on the server with no LLM cost:

```python
# Example extraction patterns (Python pseudocode)
PATTERNS = {
    "icd10":          r"[A-TV-Z][0-9][0-9AB]\.?[0-9A-TV-Z]{0,4}",
    "cpt":            r"\b[0-9]{5}\b",
    "hcpcs":          r"\b[A-V][0-9]{4}\b",
    "npi":            r"\b[0-9]{10}\b",
    "carc":           r"(?:CO|PR|OA|PI|CR)-?\s*[0-9]{1,3}",
    "rarc":           r"(?:M|N|MA|RA)[A-Z]?[0-9]{1,4}",
    "currency":       r"\$[\d,]+\.?\d{0,2}",
    "date":           r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
    "phone":          r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    "claim_number":   r"(?:Claim|Reference|Ref)\s*#?\s*:?\s*([A-Z0-9-]+)",
    "member_id":      r"(?:Member|ID|Subscriber)\s*#?\s*:?\s*([A-Z0-9-]+)",
    "group_number":   r"(?:Group)\s*#?\s*:?\s*([A-Z0-9-]+)",
    "plan_number":    r"(?:Plan|Policy)\s*#?\s*:?\s*([A-Z0-9-]+)",
}
```

**Pass 2 — LLM-Powered Extraction (Structured Output)**

For entities that require contextual understanding (denial reason narratives, provider names, plan provisions cited), we send the document text + Pass 1 results to the LLM with a structured output schema:

```json
{
  "system": "You are a medical billing document parser. Extract the following entities from the insurance document. Return ONLY the JSON schema below. If a field is not found, return null.",
  "output_schema": {
    "denial_reason_narrative": "string",
    "plan_provision_cited": "string",
    "clinical_criteria_cited": "string",
    "prior_auth_status": "enum: granted | denied | not_requested | expired | not_required | unknown",
    "treating_provider_name": "string",
    "patient_full_name": "string",
    "network_status": "enum: in_network | out_of_network | unknown",
    "expedited_review_available": "boolean",
    "...": "..."
  }
}
```

**Why hybrid:** Pass 1 is free and instant. Pass 2 only runs for fields that require reasoning. This minimises LLM API cost.

### 4.4 Stage 3: Enrichment — See Multi-Agent Architecture (Section 5)

### 4.5 Stage 4: Analysis

**Root Cause Classifier (Hybrid Rule + AI)**

Six cause categories with rule-based pre-classification + LLM confirmation:

| Category | Rule Triggers | CARC Code Patterns |
|---|---|---|
| Medical Necessity | CARC 50, 56, 58; narrative contains "not medically necessary" | CO-50, CO-56, CO-58 |
| Coding / Billing Error | CARC 4, 16, 97, 181; mismatched ICD+CPT pairs | CO-4, CO-16, CO-97 |
| Prior Authorization | CARC 197; narrative contains "authorization", "precertification" | CO-197, CO-15 |
| Network / Eligibility | CARC 109, 27; "out-of-network", "not eligible" | PR-27, CO-109 |
| Benefit Limit | CARC 119, 151; "maximum", "frequency", "benefit limit" | CO-119, CO-151 |
| Administrative / Technical | CARC 16, 252; "information missing", "timely filing" | CO-16, CO-252, CO-29 |

```
Classifier flow:
1. Check CARC codes against rule table → assign preliminary category
2. Check denial narrative keywords → confirm or override
3. If ambiguous → send to LLM with full context for final classification
4. Output: { category, confidence_score, responsible_party, reasoning }
```

**Denial Letter Completeness Checker**

Cross-references extracted entities against a checklist of legally required fields:

```
ACA §2719 / ERISA §503 Required Fields:
□ Specific denial reason (not vague)      → check denial_reason_narrative
□ Plan provision cited                     → check plan_provision_cited
□ Clinical criteria used (if med. nec.)    → check clinical_criteria_cited
□ Right to internal appeal stated          → NLP scan for "appeal" + "right"
□ Internal appeal deadline stated          → check internal_appeal_deadline_stated
□ Right to external review stated          → NLP scan for "external" + "independent"
□ Expedited review mentioned               → check expedited_review_available
□ Insurer contact info present             → check phone + address
□ Right to request full case file          → NLP scan for "documents" + "request"
□ Plain language notice                    → readability score (Flesch-Kincaid)

Indiana-specific additions (IDOI):
□ IDOI complaint reference                 → NLP scan for "Department of Insurance"
□ State consumer assistance reference      → NLP scan for "consumer assistance"
```

If fields are missing → flag as **"Deficient Denial Letter"** → surface IDOI escalation CTA.

**Deadline Calculator**

```
Inputs:
  - date_of_denial (extracted)
  - plan_type (from wizard: ACA marketplace / employer ERISA / employer fully-insured / Medicaid)
  - state (from wizard)

Logic:
  IF plan_type == "ERISA":
    internal_appeal_deadline = date_of_denial + 60 days (pre-service)
                             = date_of_denial + 180 days (post-service)
    external_review_deadline = After exhausting internal (no fixed days)
  ELIF plan_type in ["ACA marketplace", "fully-insured"]:
    internal_appeal_deadline = date_of_denial + 180 days
    external_review_deadline = date_of_denial + 4 months
  ELIF plan_type == "Medicaid":
    internal_appeal_deadline = state-specific (lookup via agent)

  expedited_available = IF urgency == true → 72 hours from filing

Output:
  {
    internal_deadline: "2026-09-24",
    external_deadline: "2026-07-28",
    expedited_available: true,
    days_remaining_internal: 142,
    days_remaining_external: 84,
    ics_event: <generated .ics file content>
  }
```

---

## 5. Multi-Agent Architecture

### 5.1 Agent Orchestration Overview

We use an **orchestrator pattern** where a central Orchestrator Agent dispatches tasks to specialised tool-equipped agents, gathers their results, and feeds them into the analysis pipeline.

```
                         ┌──────────────────────┐
                         │   ORCHESTRATOR AGENT  │
                         │   (Central brain)     │
                         │                       │
                         │  Receives: Claim Obj  │
                         │  Dispatches: Tasks    │
                         │  Returns: Enriched    │
                         │           Claim Obj   │
                         └───────────┬───────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
  │  CODE LOOKUP      │  │  REGULATION       │  │  STATE RULES      │
  │  AGENT            │  │  AGENT            │  │  AGENT            │
  │                   │  │                   │  │                   │
  │  Tools:           │  │  Tools:           │  │  Tools:           │
  │  - CMS ICD API    │  │  - eCFR search    │  │  - IDOI scraper   │
  │  - CMS HCPCS API  │  │  - DOL ERISA DB   │  │  - State DOI DB   │
  │  - CARC/RARC DB   │  │  - HHS ACA regs   │  │  - Consumer asst. │
  │  - NPI registry   │  │  - CMS coverage   │  │    lookup         │
  └───────────────────┘  └───────────────────┘  └───────────────────┘
              │                      │                      │
              │                      │                      │
              ▼                      ▼                      ▼
  ┌───────────────────┐  ┌───────────────────┐
  │  ANALYSIS AGENT   │  │  OUTPUT AGENT     │
  │                   │  │                   │
  │  - Root cause     │  │  - Summary gen    │
  │  - Completeness   │  │  - Appeal letter  │
  │  - Probability    │  │  - Provider brief │
  │  - Deadlines      │  │  - Action plan    │
  └───────────────────┘  └───────────────────┘
```

### 5.2 Agent Definitions

#### Agent 1: Orchestrator Agent

**Role:** Central coordinator. Receives the raw Claim Object from the extraction pipeline, determines which lookup agents to dispatch, waits for their results, then triggers the analysis and output agents in sequence.

**LLM:** Google Gemini 2.5 Flash (free tier — fast, cheap, good for orchestration)

**Behaviour:**
```
1. Receive claim_object from extraction pipeline
2. Inspect extracted codes:
   - If ICD/CPT/HCPCS codes present → dispatch Code Lookup Agent
   - If CARC/RARC codes present → dispatch Code Lookup Agent
   - Always → dispatch Regulation Agent (need appeal rules)
   - Always → dispatch State Rules Agent (need state-specific deadlines)
3. Wait for all agents to return (parallel execution)
4. Merge enrichment data into claim_object
5. Dispatch Analysis Agent with enriched claim_object
6. Dispatch Output Agent with analysis results
7. Return final response to API layer
```

#### Agent 2: Code Lookup Agent

**Role:** Resolves every billing and denial code to its authoritative definition. No local code database.

**LLM:** Gemini 2.5 Flash

**Tools:**

| Tool Name | What It Does | Source | Cost |
|---|---|---|---|
| `lookup_icd10` | Fetches ICD-10-CM code description | CMS.gov ICD-10 lookup / WHO ICD API | Free |
| `lookup_cpt_hcpcs` | Fetches CPT/HCPCS code description | CMS.gov HCPCS annual data files | Free |
| `lookup_carc` | Fetches Claim Adjustment Reason Code description | WPC CARC list (public), CMS X12 tables | Free |
| `lookup_rarc` | Fetches Remittance Advice Remark Code description | WPC RARC list (public) | Free |
| `lookup_npi` | Fetches provider details from NPI registry | NPPES NPI Registry API (`https://npiregistry.cms.hhs.gov/api/`) | Free |
| `lookup_place_of_service` | Resolves POS codes | CMS Place of Service code list | Free |
| `web_search` | Fallback search for any code not found in structured APIs | Google Search API (100 queries/day free) or SerpAPI | Free tier |

**Example tool execution:**
```
Input:  CARC code "CO-50"
Tool:   lookup_carc("50")
Output: {
  code: "50",
  description: "These are non-covered services because this is not deemed a medical necessity under the payer's definition.",
  group: "CO (Contractual Obligation)",
  common_cause: "Insurer disagrees with treating physician's medical necessity determination",
  plain_english: "Your insurance company says they don't think this treatment was medically necessary."
}
```

#### Agent 3: Regulation Agent

**Role:** Fetches the specific federal regulations and legal provisions relevant to this claim.

**LLM:** Gemini 2.5 Flash

**Tools:**

| Tool Name | What It Does | Source | Cost |
|---|---|---|---|
| `search_ecfr` | Searches the Electronic Code of Federal Regulations | `https://www.ecfr.gov/api/` (free, public API) | Free |
| `search_erisa` | Fetches ERISA §502/§503 appeal requirements | DOL.gov ERISA enforcement page | Free |
| `search_aca_provisions` | Fetches ACA §2719 internal/external review rules | HHS.gov, CMS marketplace regs | Free |
| `search_cms_coverage` | Searches CMS National Coverage Determinations | CMS Medicare Coverage Database | Free |
| `web_search` | General regulatory search fallback | Google Search API | Free tier |

**Behaviour:**
```
Given: claim_object.erisa_or_state_regulated, claim_object.plan_type

IF erisa:
  → search_erisa() for §503 claims procedure requirements
  → search_ecfr() for 29 CFR §2560.503-1 (claims procedure regulation)
  → return { appeal_process, deadlines, required_notices, legal_citations }

IF aca_marketplace or fully_insured:
  → search_aca_provisions() for §2719 internal/external review
  → search_ecfr() for 45 CFR §147.136 (internal claims and appeals)
  → return { appeal_process, deadlines, external_review_entity, legal_citations }

IF medical_necessity denial:
  → search_cms_coverage() for relevant LCD/NCD
  → return { coverage_determination, criteria, lcd_id }
```

#### Agent 4: State Rules Agent

**Role:** Fetches state-specific insurance regulations, deadlines, and consumer resources. Indiana-first implementation.

**LLM:** Gemini 2.5 Flash

**Tools:**

| Tool Name | What It Does | Source | Cost |
|---|---|---|---|
| `search_idoi` | Searches Indiana Department of Insurance regulations and consumer guides | IDOI website (`https://www.in.gov/idoi/`) | Free (web scrape) |
| `get_state_doi_contact` | Returns state DOI contact block (phone, address, complaint URL) | Maintained as a small JSON config file (50 states) — the ONE static file in the system | Free |
| `search_state_appeal_rules` | Searches for state-specific external review procedures | State DOI websites | Free (web scrape) |
| `web_search` | Fallback for state-specific regulatory questions | Google Search API | Free tier |

**The one exception to "no local data":** We maintain a single, small JSON file (~50 entries) mapping each state to its DOI contact information (phone, address, complaint URL). This data changes very rarely and is critical for the IDOI/DOI routing card. Everything else is fetched live.

#### Agent 5: Analysis Agent

**Role:** Takes the enriched Claim Object and produces all analytical outputs.

**LLM:** Gemini 2.5 Flash (with structured output)

**No external tools** — this agent operates purely on the data already gathered by agents 2-4.

**Outputs:**
```json
{
  "root_cause": {
    "category": "prior_authorization",
    "confidence": 0.92,
    "responsible_party": "provider_billing_office",
    "reasoning": "CARC 197 indicates missing precertification. The EOB shows no prior auth number. The provider was responsible for obtaining authorization before the procedure."
  },
  "denial_completeness": {
    "score": 0.76,
    "missing_fields": ["clinical_criteria_cited", "state_commissioner_info"],
    "deficient": true,
    "escalation_available": true
  },
  "deadlines": {
    "internal_appeal": { "date": "2026-09-24", "days_remaining": 142, "source": "ACA §2719 — 180 days" },
    "external_review": { "date": "2026-07-28", "days_remaining": 84, "source": "ACA §2719 — 4 months" },
    "expedited": { "available": true, "turnaround": "72 hours", "qualifier": "Patient is currently receiving treatment" }
  },
  "approval_probability": {
    "score": 0.78,
    "reasoning": "Prior authorization denials have a 78% overturn rate when the provider submits retroactive authorization with clinical documentation. Source: CMS appeals data.",
    "factors": ["+Provider error (high overturn)", "+Clinical documentation available", "-No prior appeal filed yet"]
  },
  "severity_triage": "time_sensitive",
  "assumptions": [
    { "assumption": "Plan is ACA-compliant (not grandfathered)", "confidence": 0.85 },
    { "assumption": "Provider is willing to submit retroactive auth", "confidence": 0.70 }
  ]
}
```

#### Agent 6: Output Generation Agent

**Role:** Takes analysis results and generates all user-facing content.

**LLM:** Gemini 2.5 Flash

**Outputs:**

| Output | Description |
|---|---|
| `plain_english_summary` | One-paragraph human-readable denial explanation |
| `action_checklist` | Numbered steps with "Why?" expanders for each step |
| `appeal_letter_draft` | Formal appeal letter citing regulations and clinical facts |
| `provider_message_draft` | Message to send to provider's billing office |
| `insurer_message_draft` | Message to send to insurer's member services |
| `provider_brief` | One-page formatted summary for the treating physician |
| `regulatory_routing_card` | ERISA vs. IDOI routing with contact blocks |

### 5.3 Agent Communication Protocol

Agents communicate via structured JSON messages through the Orchestrator. No agent talks directly to another agent.

```
Orchestrator → Agent: {
  "task": "lookup_codes",
  "claim_id": "temp_abc123",
  "codes": {
    "icd10": ["M54.5", "G89.29"],
    "cpt": ["62323"],
    "carc": ["50"],
    "npi": ["1234567890"]
  }
}

Agent → Orchestrator: {
  "task": "lookup_codes",
  "status": "complete",
  "results": {
    "icd10": { "M54.5": { "description": "Low back pain", "plain_english": "..." }, ... },
    "cpt": { "62323": { "description": "Lumbar epidural steroid injection", ... } },
    "carc": { "50": { "description": "...", "plain_english": "...", "common_fix": "..." } },
    "npi": { "1234567890": { "name": "Dr. Smith", "specialty": "Pain Management", ... } }
  },
  "sources": [
    { "entity": "M54.5", "source": "CMS ICD-10-CM 2026", "url": "https://..." },
    ...
  ]
}
```

### 5.4 LLM Provider Strategy

| Role | Primary Model | Fallback | Why |
|---|---|---|---|
| Orchestrator | Gemini 2.5 Flash | Gemini 2.0 Flash | Free tier, fast, good reasoning |
| Code Lookup Agent | Gemini 2.5 Flash | Llama 3.3 70B via OpenRouter | Free tier |
| Regulation Agent | Gemini 2.5 Flash | Gemini 2.0 Flash | Free tier |
| State Rules Agent | Gemini 2.5 Flash | Gemini 2.0 Flash | Free tier |
| Analysis Agent | Gemini 2.5 Flash | Gemini 2.5 Pro (paid, if budget allows) | Needs best reasoning |
| Output Generation | Gemini 2.5 Flash | Llama 3.3 via OpenRouter | Free tier, writing quality |
| Entity Extraction (Pass 2) | Gemini 2.5 Flash | Gemini 2.0 Flash | Structured output support |

**Total LLM cost for MVP: $0** using Gemini free tier (15 RPM, 1M tokens/day for Flash).

---

## 6. API Design

### 6.1 API Architecture

The backend exposes a **RESTful API** with the following endpoint groups. All endpoints are stateless — no database, no sessions. The entire claim analysis is performed per-request and the result is returned in a single response (or streamed for long operations).

### 6.2 Endpoint Specification

#### Group 1: Document Processing

```
POST /api/v1/documents/upload
  Description: Upload one or more documents. Returns extracted text and metadata.
  Body: multipart/form-data
    - files[]: File[] (PDF, JPG, PNG) — max 10MB each, max 5 files
  Response: {
    upload_id: string,
    documents: [{
      doc_id: string,
      type: "denial_letter" | "eob" | "hospital_bill" | "insurance_card" | "other",
      text_extracted: string,
      ocr_used: boolean,
      ocr_confidence: number,
      page_count: number
    }]
  }
```

```
POST /api/v1/documents/extract
  Description: Extract entities from uploaded document text.
  Body: {
    upload_id: string,
    documents: [{ doc_id, text_extracted }],
    plan_context: {                        ← from Plan Type Wizard
      plan_type: "employer" | "marketplace" | "medicaid",
      regulation_type: "erisa" | "fully_insured" | "state_medicaid",
      state: "IN"                          ← 2-letter state code
    }
  }
  Response: {
    claim_object: <full entity schema from Section 3>,
    extraction_confidence: {
      overall: number,
      per_field: { [field_name]: number }
    },
    warnings: string[]                     ← e.g., "Could not find NPI number"
  }
```

#### Group 2: Enrichment & Analysis

```
POST /api/v1/claims/analyze
  Description: Core analysis endpoint. Takes extracted claim object, runs all agents
               (code lookup, regulation, state rules, analysis), returns full results.
               This is the main orchestration call.
  Body: {
    claim_object: <from /documents/extract>,
    plan_context: { plan_type, regulation_type, state }
  }
  Response: {
    enrichment: {
      codes: { [code]: { description, plain_english, source_url } },
      regulations: { applicable_laws: [], appeal_rules: {}, legal_citations: [] },
      state_rules: { doi_contact: {}, state_deadlines: {}, consumer_resources: [] }
    },
    analysis: {
      root_cause: { category, confidence, responsible_party, reasoning },
      denial_completeness: { score, missing_fields, deficient, escalation_available },
      deadlines: { internal, external, expedited },
      approval_probability: { score, reasoning, factors },
      severity_triage: "urgent" | "time_sensitive" | "routine",
      assumptions: [{ assumption, confidence }]
    },
    sources: [{ entity, source_name, url, accessed_at }]
  }
```

```
POST /api/v1/claims/analyze/stream
  Description: Same as /analyze but uses Server-Sent Events (SSE) to stream
               partial results as each agent completes. This lets the frontend
               progressively render the UI.
  Body: <same as /analyze>
  Response: SSE stream with events:
    event: extraction_complete     → { claim_object }
    event: codes_enriched          → { codes }
    event: regulations_enriched    → { regulations }
    event: state_rules_enriched    → { state_rules }
    event: analysis_complete       → { root_cause, deadlines, probability, ... }
    event: done                    → { full_response }
```

#### Group 3: Output Generation

```
POST /api/v1/outputs/summary
  Description: Generate plain-English denial summary.
  Body: { claim_object, analysis }
  Response: { summary_text: string, reading_level: "6th grade" | "8th grade" | ... }
```

```
POST /api/v1/outputs/action-checklist
  Description: Generate numbered action steps with Why-expanders.
  Body: { claim_object, analysis }
  Response: {
    steps: [{
      number: 1,
      action: "Contact your provider's billing office",
      detail: "Ask them to submit retroactive prior authorization for CPT 62323",
      why: "The denial was caused by missing prior authorization. Your provider was responsible for obtaining this before the procedure. Most providers can request retroactive auth.",
      responsible_party: "provider",
      expected_timeline: "3-7 business days",
      contact: { name, phone, address }  ← if known
    }, ...]
  }
```

```
POST /api/v1/outputs/appeal-letter
  Description: Generate 3 output documents — appeal letter, provider message, insurer message.
  Body: {
    claim_object, analysis,
    patient_info: { name, address, phone, email }  ← user provides in UI
  }
  Response: {
    appeal_letter: { text: string, format: "markdown" },
    provider_message: { text: string, format: "markdown" },
    insurer_message: { text: string, format: "markdown" },
    legal_citations: [{ law, section, relevance }]
  }
```

```
POST /api/v1/outputs/provider-brief
  Description: Generate one-page provider-formatted summary.
  Body: { claim_object, analysis }
  Response: { brief_text: string, format: "markdown", pdf_ready: boolean }
```

```
POST /api/v1/outputs/deadlines
  Description: Return calculated deadlines with .ics calendar export.
  Body: { claim_object, analysis }
  Response: {
    deadlines: [{ type, date, days_remaining, source_law, ics_data: string }],
    reminders: { email_opt_in_url: string }
  }
```

```
GET /api/v1/codes/lookup?code={code}&type={icd10|cpt|carc|rarc|hcpcs}
  Description: Standalone code lookup (for the search library feature).
  Response: {
    code, type, description, plain_english, common_denial_context,
    source: { name, url }
  }
```

#### Group 4: Utility

```
POST /api/v1/wizard/plan-type
  Description: Returns regulatory routing based on 3-question wizard answers.
  Body: {
    source: "employer" | "marketplace" | "medicaid" | "individual",
    employer_plan_type: "erisa" | "fully_insured" | "unknown",
    state: "IN"
  }
  Response: {
    regulation_type: "erisa" | "aca_marketplace" | "state_fully_insured" | "medicaid",
    appeal_path: "federal_erisa" | "state_external_review" | "state_medicaid",
    primary_regulator: { name, url, phone },
    applicable_laws: ["ERISA §503", "29 CFR §2560.503-1"],
    indiana_specific: { idoi_contact: {...}, idoi_complaint_url: "..." }
  }
```

```
POST /api/v1/export/pdf
  Description: Generate PDF from any markdown output (appeal letter, brief, summary).
  Body: { content: string, format: "appeal_letter" | "provider_brief" | "summary" }
  Response: application/pdf binary stream
```

```
POST /api/v1/export/ics
  Description: Generate .ics calendar event for a deadline.
  Body: { event_title, event_date, description, reminder_days_before: [30, 7] }
  Response: text/calendar
```

---

## 7. Feature-to-API Mapping

Every product feature maps to specific API endpoints. This table is the bridge between the product plan and the technical implementation.

| Feature | Primary API Endpoint(s) | Agents Involved |
|---|---|---|
| Document Upload | `POST /documents/upload` | None (direct processing) |
| Plan Type Wizard | `POST /wizard/plan-type` | None (rules engine) |
| Severity Triage Badge | `POST /claims/analyze` → `severity_triage` | Analysis Agent |
| Plain-English Denial Summary | `POST /outputs/summary` | Output Agent |
| Claim Lifecycle Pipeline UI | `POST /claims/analyze` → `root_cause` | Analysis Agent |
| Denial Code Classifier | `POST /claims/analyze` → `root_cause` | Code Lookup + Analysis Agents |
| Bill Breakdown Explainer | `POST /claims/analyze` → `enrichment.codes` | Code Lookup Agent |
| Responsibility Attribution | `POST /claims/analyze` → `root_cause.responsible_party` | Analysis Agent |
| Assumptions & Gaps Panel | `POST /claims/analyze` → `assumptions` | Analysis Agent |
| Denial Letter Completeness Checker | `POST /claims/analyze` → `denial_completeness` | Analysis Agent |
| Root Cause Action Checklist | `POST /outputs/action-checklist` | Output Agent |
| Approval Probability Score | `POST /claims/analyze` → `approval_probability` | Analysis Agent |
| ERISA vs. IDOI Routing Card | `POST /wizard/plan-type` + `POST /claims/analyze` | State Rules Agent |
| Appeal Deadline Calculator | `POST /outputs/deadlines` | Analysis Agent |
| .ics Calendar Export | `POST /export/ics` | None (utility) |
| Appeal Letter Generator (3 tabs) | `POST /outputs/appeal-letter` | Output Agent |
| Share With Provider Summary | `POST /outputs/provider-brief` | Output Agent |
| PDF Export | `POST /export/pdf` | None (utility) |
| Code & Term Lookup Library | `GET /codes/lookup` | Code Lookup Agent |
| Multi-Document Stitching | `POST /documents/extract` (multi-doc matching logic) | None (pipeline logic) |
| Aggregate Denial Dashboard | Future: `GET /analytics/trends` | Future scope |
| Email / SMS Reminders | `POST /outputs/deadlines` → `reminders.email_opt_in_url` | Future: SendGrid/Twilio |

---

## 8. End-to-End Flow Orchestration

### 8.1 Complete Request Lifecycle

This is the full sequence of what happens when a user uploads a document and receives their results.

```
USER ACTION                         FRONTEND                           BACKEND
===========                         ========                           =======

1. User uploads document(s)
   │
   ├──→ Show upload progress ──────→ POST /documents/upload
   │                                  │
   │                                  ├── Detect file type (PDF/image)
   │                                  ├── Digital PDF → pdf-parse → text
   │                                  ├── Scanned/Image → Tesseract OCR → text
   │                                  ├── Return extracted text + doc metadata
   │                                  │
   │    ◄── Render OCR preview ◄─────┘
   │
2. User answers Plan Type Wizard (3 questions)
   │
   ├──→ Send answers ─────────────→ POST /wizard/plan-type
   │                                  │
   │                                  ├── Rules engine determines regulation path
   │                                  ├── Returns plan_context object
   │                                  │
   │    ◄── Show plan routing ◄──────┘
   │
3. User clicks "Analyze My Claim"
   │
   ├──→ Show loading/streaming ───→ POST /claims/analyze/stream (SSE)
   │                                  │
   │                                  ├──[1] Entity extraction (regex + LLM)
   │                                  │     → emit: extraction_complete
   │    ◄── Render entity table ◄────┘
   │                                  │
   │                                  ├──[2] Orchestrator dispatches 3 agents in PARALLEL:
   │                                  │     ├── Code Lookup Agent (all codes)
   │                                  │     ├── Regulation Agent (federal rules)
   │                                  │     └── State Rules Agent (IDOI)
   │                                  │
   │                                  │     (agents run concurrently, ~2-5 seconds)
   │                                  │
   │                                  │     → emit: codes_enriched
   │    ◄── Render code cards ◄──────┘
   │                                  │     → emit: regulations_enriched
   │    ◄── Show legal citations ◄───┘
   │                                  │     → emit: state_rules_enriched
   │    ◄── Show IDOI card ◄─────────┘
   │                                  │
   │                                  ├──[3] Analysis Agent (sequential, needs all enrichment)
   │                                  │     → Root cause classification
   │                                  │     → Completeness check
   │                                  │     → Deadline calculation
   │                                  │     → Probability estimation
   │                                  │     → emit: analysis_complete
   │    ◄── Render full dashboard ◄──┘
   │                                  │
   │                                  └── emit: done
   │
4. User views results dashboard
   │
   ├── Clicks "Generate Appeal Letter"
   │     └──→ POST /outputs/appeal-letter → render 3 tabs
   │
   ├── Clicks "View Action Checklist"
   │     └──→ POST /outputs/action-checklist → render numbered steps
   │
   ├── Clicks "Download Provider Brief"
   │     └──→ POST /outputs/provider-brief → POST /export/pdf → download
   │
   ├── Clicks "Add Deadlines to Calendar"
   │     └──→ POST /export/ics → download .ics file
   │
   └── Clicks "Look Up a Code"
         └──→ GET /codes/lookup?code=M54.5&type=icd10 → render card
```

### 8.2 Timing Budget

| Stage | Expected Duration | Notes |
|---|---|---|
| Upload + OCR | 1-3 seconds | Tesseract.js runs client-side; server PDF parsing is fast |
| Entity Extraction | 2-4 seconds | Regex pass is instant; LLM pass ~2-3s |
| Agent Enrichment (parallel) | 3-6 seconds | 3 agents run concurrently; web lookups are the bottleneck |
| Analysis | 2-3 seconds | Single LLM call with structured output |
| Output Generation | 1-2 seconds per output | On-demand, only when user clicks |
| **Total time to dashboard** | **~8-16 seconds** | SSE streaming means user sees partial results within 3-5s |

---

## 9. Frontend Architecture

### 9.1 Technology Stack

| Layer | Technology | Why |
|---|---|---|
| Framework | Next.js 14 (App Router) | Free Vercel hosting, SSR, streaming, API routes |
| UI Library | React 18 | Component-based, huge ecosystem |
| Styling | Tailwind CSS | Utility-first, fast development, small bundle |
| Component Library | shadcn/ui | High-quality, accessible, customisable |
| State Management | React Context + useReducer | No external deps needed for this scale |
| File Upload | react-dropzone | Drag-and-drop, paste, camera capture |
| PDF Generation | @react-pdf/renderer or html2pdf.js | Client-side PDF export |
| Calendar Export | ics.js | Generate .ics files client-side |
| Markdown Rendering | react-markdown | Render appeal letters and briefs |
| Streaming | EventSource API (native) | SSE consumption for progressive rendering |
| OCR (client-side) | Tesseract.js | Free, no API key, runs in-browser |

### 9.2 Page Structure

```
/                           → Landing page (problem statement, demo CTA)
/analyze                    → Main application flow
  ├── Step 1: Upload        → Drag-and-drop zone, camera capture, multi-file
  ├── Step 2: Plan Wizard   → 3-question routing form
  ├── Step 3: Processing    → Streaming progress with partial renders
  └── Step 4: Dashboard     → Full results view
      ├── Tab: Summary      → Plain-English explanation + severity badge
      ├── Tab: Debug View   → Claim pipeline UI (green/yellow/red)
      ├── Tab: Codes        → All codes decoded with source links
      ├── Tab: Actions      → Checklist with Why-expanders
      ├── Tab: Appeals      → 3-subtab letter generator
      ├── Tab: Deadlines    → Countdown timers + .ics export
      ├── Tab: Completeness → Missing fields checklist + IDOI CTA
      └── Tab: Details      → Full entity table + assumptions panel
/lookup                     → Standalone code search tool
/about                      → Project info, disclaimers, resources
```

### 9.3 Key UI Components

**Claim Pipeline Component (Debug View)**
```
  ┌──────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ Billed│───→│ Received │───→│ Reviewed │──X─→│ DENIED  │───→│ Appeal?  │
  │  ✅   │    │    ✅    │    │    ✅    │    │   🔴    │    │   ⬜    │
  └──────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                   │
                                     ┌─────────────┘
                                     ▼
                              ┌──────────────┐
                              │ FAILURE POINT│
                              │ Prior Auth   │
                              │ Missing      │
                              │              │
                              │ Responsible: │
                              │ Provider     │
                              └──────────────┘
```

**Assumptions & Gaps Panel**
```
  ┌─────────────────────────────────────────────────────┐
  │  ⚠️  Assumptions & Uncertainties                     │
  ├─────────────────────────────────────────────────────┤
  │  ● Plan is ACA-compliant (not grandfathered)   85%  │
  │  ● Provider is willing to submit retro auth    70%  │
  │  ● This is a post-service claim                95%  │
  │                                                      │
  │  📌 These assumptions affect the recommended         │
  │     actions. If any are incorrect, results may vary. │
  └─────────────────────────────────────────────────────┘
```

---

## 10. Infrastructure & Free-Tier Hosting Strategy

### 10.1 Hosting Stack (All Free Tier)

| Service | Provider | What It Hosts | Free Tier Limits |
|---|---|---|---|
| Frontend + API Routes | **Vercel** (Hobby plan) | Next.js app, serverless API functions | 100 GB bandwidth/month, 10s function timeout, 1000 function invocations/day |
| Backend API (long-running agents) | **Render** (Free tier) | Python FastAPI / Node.js Express server for agent orchestration | 750 hours/month, spins down after 15 min inactivity, 512 MB RAM |
| LLM API | **Google Gemini** (Free tier) | All agent LLM calls | 15 RPM, 1M tokens/day, 1500 req/day for Gemini 2.5 Flash |
| OCR (fallback) | **Google Cloud Vision** | Scanned document OCR | 1000 units/month free |
| Email Reminders (future) | **Resend** or **SendGrid** | Deadline reminder emails | Resend: 3000 emails/month; SendGrid: 100/day |
| SMS Reminders (future) | **Twilio** | Deadline SMS reminders | Trial credit (~$15) |
| Domain (optional) | **Vercel** | `.vercel.app` subdomain | Free |
| Monitoring | **Vercel Analytics** + **Sentry** (free tier) | Error tracking, performance | Free tier for both |

### 10.2 Architecture Diagram (Infrastructure)

```
┌──────────────────────────────────────────────────────────────────────┐
│                            USER BROWSER                              │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐                │
│  │ Tesseract.js│  │ React UI    │  │ EventSource  │                │
│  │ (OCR)       │  │ (Next.js)   │  │ (SSE client) │                │
│  └─────────────┘  └─────────────┘  └──────────────┘                │
│                                                                      │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ HTTPS
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         VERCEL (Free Hobby)                          │
│                                                                      │
│  ┌──────────────────────────────────┐  ┌──────────────────────────┐ │
│  │  Next.js Frontend (SSR + Static) │  │  API Routes (Serverless) │ │
│  │  - Pages                         │  │  - /api/documents/*      │ │
│  │  - Components                    │  │  - /api/wizard/*         │ │
│  │  - Static assets                 │  │  - /api/codes/*          │ │
│  │                                  │  │  - /api/export/*         │ │
│  └──────────────────────────────────┘  └───────────┬──────────────┘ │
│                                                     │                │
└─────────────────────────────────────────────────────┼────────────────┘
                                                      │ HTTPS
                                                      ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       RENDER (Free Tier)                             │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FastAPI / Express Backend                                    │   │
│  │                                                               │   │
│  │  POST /api/v1/claims/analyze/stream                           │   │
│  │    │                                                          │   │
│  │    ├── Entity Extraction Module                               │   │
│  │    │                                                          │   │
│  │    ├── Orchestrator Agent ─────────────────────────┐          │   │
│  │    │                                               │          │   │
│  │    │    ┌────────────────┐ ┌───────────────┐ ┌────┴──────┐   │   │
│  │    │    │ Code Lookup    │ │ Regulation    │ │ State     │   │   │
│  │    │    │ Agent          │ │ Agent         │ │ Rules Agt │   │   │
│  │    │    └───────┬────────┘ └──────┬────────┘ └────┬──────┘   │   │
│  │    │            │                 │               │           │   │
│  │    │    ┌───────▼─────────────────▼───────────────▼───────┐   │   │
│  │    │    │              TOOL EXECUTION LAYER                │   │   │
│  │    │    │  - CMS APIs        - eCFR API    - IDOI scraper │   │   │
│  │    │    │  - NPI Registry    - DOL.gov     - State DOI    │   │   │
│  │    │    │  - CARC/RARC DB    - HHS.gov     - Web search   │   │   │
│  │    │    └─────────────────────────────────────────────────┘   │   │
│  │    │                                                          │   │
│  │    ├── Analysis Agent                                         │   │
│  │    ├── Output Agent                                           │   │
│  │    └── SSE Response Stream                                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                               │
                               │ HTTPS (outbound)
                               ▼
         ┌─────────────────────────────────────────────┐
         │           EXTERNAL SERVICES                  │
         │                                              │
         │  ● Google Gemini API (free tier)             │
         │  ● CMS.gov APIs (free, public)              │
         │  ● NPPES NPI Registry (free, public)        │
         │  ● eCFR.gov API (free, public)              │
         │  ● Google Cloud Vision (1000/mo free)       │
         │  ● Google Search API (100/day free)         │
         │                                              │
         └─────────────────────────────────────────────┘
```

### 10.3 Cold Start Mitigation

Render free tier spins down after 15 minutes of inactivity (~30-50 second cold start). Mitigations:

1. **Health check ping:** Set up a free cron job (cron-job.org) to hit the `/health` endpoint every 14 minutes to keep the server warm during peak hours
2. **Client-side OCR:** Tesseract.js runs in the browser, so OCR doesn't depend on the backend being warm
3. **Vercel API routes:** Lightweight endpoints (plan wizard, code lookup, PDF/ICS export) run on Vercel serverless functions, which have near-instant cold starts
4. **Only the heavy `/claims/analyze` route** hits Render — this is the one that needs long-running agent orchestration

### 10.4 No Database — Stateless by Design

The system is fully stateless in V1:

- No user accounts, no login
- No data persisted between sessions
- Each analysis is a self-contained request → response
- Documents are held in server memory only during processing, then discarded
- Generated letters are rendered in the frontend and exported as PDF client-side

**Future state (V2):** If we add user accounts, deadline reminders, or a provider portal, we would add:
- **Supabase** (free tier: 500 MB Postgres, unlimited API requests) for user data + claim history
- **Upstash Redis** (free tier: 256 MB, 500K commands/month) for caching code lookups and rate limiting

---

## 11. Repository Structure

```
claim-debugger/
│
├── README.md
├── implementation_plan.md              ← This document
│
├── frontend/                           ← Next.js app (deployed to Vercel)
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   │
│   ├── app/
│   │   ├── layout.tsx                  ← Root layout (nav, footer, theme)
│   │   ├── page.tsx                    ← Landing page
│   │   ├── analyze/
│   │   │   └── page.tsx               ← Main analysis flow (upload → wizard → results)
│   │   ├── lookup/
│   │   │   └── page.tsx               ← Standalone code lookup tool
│   │   └── about/
│   │       └── page.tsx               ← About, disclaimers, resources
│   │
│   ├── components/
│   │   ├── upload/
│   │   │   ├── DropZone.tsx           ← Multi-file drag-and-drop with camera capture
│   │   │   ├── DocumentPreview.tsx    ← OCR preview and text confirmation
│   │   │   └── MultiDocStitcher.tsx   ← Visual indicator of matched documents
│   │   │
│   │   ├── wizard/
│   │   │   └── PlanTypeWizard.tsx     ← 3-question routing form
│   │   │
│   │   ├── dashboard/
│   │   │   ├── SeverityBadge.tsx      ← Urgent / Time-Sensitive / Routine
│   │   │   ├── DenialSummary.tsx      ← Plain-English summary card
│   │   │   ├── ClaimPipeline.tsx      ← Visual lifecycle (green/yellow/red stages)
│   │   │   ├── CodeCards.tsx          ← Decoded billing/denial codes
│   │   │   ├── RootCausePanel.tsx     ← Category + confidence + responsible party
│   │   │   ├── ActionChecklist.tsx    ← Numbered steps with Why-expanders
│   │   │   ├── DeadlineTracker.tsx    ← Countdown timers + .ics download
│   │   │   ├── CompletenessChecker.tsx ← Required fields checklist + IDOI CTA
│   │   │   ├── ProbabilityScore.tsx   ← Appeal success estimate + reasoning
│   │   │   ├── AssumptionsPanel.tsx   ← Flagged uncertainties + confidence
│   │   │   ├── RegulatoryCard.tsx     ← ERISA vs. IDOI routing with contacts
│   │   │   └── BillBreakdown.tsx      ← Line-by-line financial view
│   │   │
│   │   ├── outputs/
│   │   │   ├── AppealLetterTabs.tsx   ← 3 tabs: appeal, provider msg, insurer msg
│   │   │   ├── ProviderBrief.tsx      ← Formatted one-pager
│   │   │   └── PdfExport.tsx          ← Client-side PDF generation
│   │   │
│   │   ├── lookup/
│   │   │   └── CodeSearch.tsx         ← Search input + result card
│   │   │
│   │   └── shared/
│   │       ├── LoadingStream.tsx      ← SSE progress indicator
│   │       ├── SourceCitation.tsx     ← [Source] link badges
│   │       └── Disclaimer.tsx         ← Legal disclaimer banner
│   │
│   ├── lib/
│   │   ├── ocr.ts                     ← Tesseract.js wrapper
│   │   ├── sse-client.ts             ← EventSource hook for streaming
│   │   ├── ics-generator.ts          ← .ics file generator
│   │   └── pdf-client.ts             ← Client-side PDF export
│   │
│   └── api/                           ← Vercel serverless API routes
│       ├── documents/
│       │   └── upload/route.ts        ← File upload + text extraction
│       ├── wizard/
│       │   └── plan-type/route.ts     ← Plan type routing (rules engine)
│       ├── codes/
│       │   └── lookup/route.ts        ← Standalone code lookup
│       └── export/
│           ├── pdf/route.ts           ← Markdown → PDF conversion
│           └── ics/route.ts           ← ICS calendar file generation
│
├── backend/                            ← FastAPI app (deployed to Render)
│   ├── requirements.txt
│   ├── main.py                         ← FastAPI app entry point
│   ├── config.py                       ← Environment vars, API keys, model config
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── analyze.py             ← POST /claims/analyze + /analyze/stream
│   │   │   ├── extract.py             ← POST /documents/extract
│   │   │   ├── outputs.py             ← POST /outputs/* (summary, checklist, letters)
│   │   │   └── health.py             ← GET /health (keep-alive ping)
│   │   └── middleware/
│   │       ├── cors.py                ← CORS for Vercel ↔ Render
│   │       └── rate_limit.py          ← In-memory rate limiting
│   │
│   ├── extraction/
│   │   ├── regex_extractor.py         ← Pass 1: deterministic pattern matching
│   │   ├── llm_extractor.py           ← Pass 2: LLM-based entity extraction
│   │   ├── document_stitcher.py       ← Multi-doc matching and merging
│   │   └── schema.py                  ← Pydantic models for Claim Object
│   │
│   ├── agents/
│   │   ├── orchestrator.py            ← Central agent dispatcher
│   │   ├── code_lookup_agent.py       ← Agent 2: billing code resolution
│   │   ├── regulation_agent.py        ← Agent 3: federal regulation lookup
│   │   ├── state_rules_agent.py       ← Agent 4: state-specific rules
│   │   ├── analysis_agent.py          ← Agent 5: root cause, deadlines, probability
│   │   └── output_agent.py            ← Agent 6: summary, letters, checklist
│   │
│   ├── tools/
│   │   ├── cms_icd_lookup.py          ← Tool: CMS ICD-10 code resolution
│   │   ├── cms_hcpcs_lookup.py        ← Tool: CMS HCPCS/CPT resolution
│   │   ├── carc_rarc_lookup.py        ← Tool: CARC/RARC code resolution
│   │   ├── npi_registry.py            ← Tool: NPPES NPI lookup
│   │   ├── ecfr_search.py             ← Tool: eCFR regulation search
│   │   ├── erisa_search.py            ← Tool: DOL ERISA provisions
│   │   ├── aca_search.py              ← Tool: ACA provision lookup
│   │   ├── cms_coverage.py            ← Tool: Medicare coverage database
│   │   ├── state_doi_lookup.py        ← Tool: State DOI contact + rules
│   │   ├── idoi_search.py             ← Tool: Indiana DOI specific search
│   │   └── web_search.py             ← Tool: Google Search API fallback
│   │
│   ├── analysis/
│   │   ├── root_cause_classifier.py   ← Hybrid rule + AI classifier
│   │   ├── completeness_checker.py    ← ACA/state required fields checker
│   │   ├── deadline_calculator.py     ← Appeal deadline computation
│   │   ├── probability_estimator.py   ← Approval likelihood model
│   │   └── severity_triage.py         ← Urgency classification
│   │
│   └── data/
│       └── state_doi_contacts.json    ← The ONE static data file (50 state DOI contacts)
│
├── docs/
│   ├── api_spec.yaml                  ← OpenAPI 3.0 spec
│   └── agent_prompts/                 ← LLM prompt templates for each agent
│       ├── orchestrator.md
│       ├── code_lookup.md
│       ├── regulation.md
│       ├── state_rules.md
│       ├── analysis.md
│       └── output.md
│
└── scripts/
    ├── dev.sh                         ← Start both frontend + backend locally
    └── keep-alive.sh                  ← Cron script to ping Render health endpoint
```

---

## 12. Development Phases & Sprint Plan

### Phase 1: MVP Core (Weeks 1-4)

**Goal:** Upload a denial letter → get a plain-English explanation + root cause + action steps.

| Week | Deliverables |
|---|---|
| Week 1 | Project scaffold (Next.js + FastAPI), file upload, PDF text extraction, client-side OCR (Tesseract.js), Plan Type Wizard UI |
| Week 2 | Entity extraction pipeline (regex Pass 1 + LLM Pass 2), Claim Object schema, Code Lookup Agent + tools (CMS ICD, HCPCS, CARC/RARC, NPI) |
| Week 3 | Orchestrator Agent, Regulation Agent, State Rules Agent (IDOI), Analysis Agent (root cause classifier, deadline calculator), SSE streaming endpoint |
| Week 4 | Frontend dashboard (summary, pipeline UI, code cards, action checklist, deadlines), Output Agent (plain-English summary, action checklist), deploy to Vercel + Render |

### Phase 2: Full Feature Set (Weeks 5-8)

| Week | Deliverables |
|---|---|
| Week 5 | Appeal letter generator (3 tabs), provider brief, PDF export, .ics calendar export |
| Week 6 | Denial letter completeness checker, ERISA vs. IDOI routing card, assumptions panel, probability estimator |
| Week 7 | Multi-document stitching, bill breakdown explainer, standalone code lookup page |
| Week 8 | Severity triage badge, mobile-responsive polish, screenshot/clipboard upload, end-to-end testing |

### Phase 3: Enhancement (Weeks 9-12)

| Week | Deliverables |
|---|---|
| Week 9-10 | Email deadline reminders (Resend/SendGrid), user opt-in flow, bad faith pattern detection |
| Week 11-12 | Aggregate denial trend dashboard (anonymised), performance optimisation, accessibility audit (WCAG 2.1 AA) |

---

## 13. Security, Privacy & Compliance Notes

### V1 Posture (MVP — No Data Persistence)

Since V1 stores nothing and has no user accounts:

- **No PHI at rest:** Documents exist only in server memory during processing (~10-30 seconds), then are garbage collected
- **No HIPAA BAA required in V1:** We do not store, transmit to third parties, or retain any Protected Health Information. Documents go from user → server memory → LLM API → response → discarded
- **HTTPS everywhere:** Vercel and Render enforce TLS by default
- **No cookies, no tracking:** No analytics that could correlate with health data
- **LLM data policy:** Google Gemini free tier does NOT use API inputs for training (as of March 2026). Confirm this before launch

### Disclaimers Required in UI

```
"This tool provides informational guidance only. It does not constitute
legal, medical, or financial advice. Always consult a qualified
professional before making decisions about your healthcare or insurance
claims. The accuracy of results depends on the quality and completeness
of uploaded documents."
```

### Future Compliance (V2 — If Adding Persistence)

If we add user accounts, stored claims, or deadline reminders tied to PHI:

- Supabase Postgres with Row Level Security + encryption at rest
- HIPAA BAA with Supabase (available on Pro plan)
- HIPAA BAA with LLM provider
- Privacy policy and terms of service
- Data retention policy (auto-delete after X days)
- SOC 2 Type II (aspirational, not required for student project)

---

> **This document is the single source of truth for the Insurance Claim & Billing Debugger technical implementation. All development work should reference this plan. Update this document when architectural decisions change.**
