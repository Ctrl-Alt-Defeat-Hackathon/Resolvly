# Resolvly — Insurance Claim & Billing Debugger

> An AI-powered platform that decodes insurance denials, fetches live regulations, and generates ready-to-send appeal letters — in under 20 seconds.

---

## The Problem

Insurance denial letters are deliberately opaque. They contain codes like `CO-197`, dates, and legal citations that most patients have never seen before. Without knowing what those codes mean, which laws apply to their specific plan, and what steps to take within which deadlines, most patients simply give up — leaving billions of dollars in legitimate claims unpaid every year.

## The Solution

Resolvly takes the documents a patient already has — a denial letter, an Explanation of Benefits (EOB), and a medical bill — and turns them into a complete action plan. It live-looks up every code against authoritative federal sources (CMS, NPPES), fetches the exact regulations that apply to the patient's plan type, calculates the deadlines they're racing against, and writes the appeal letter for them. No legal knowledge required.

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- At least one LLM API key: [Groq](https://console.groq.com) (recommended, free) or [Google Gemini](https://aistudio.google.com)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create .env from the example
cp .env.example .env
# Add your GROQ_API_KEY or GEMINI_API_KEY to .env

python main.py
# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# App available at http://localhost:5173
```

---

## How It Works

A patient uploads three documents, answers two questions about their plan, and clicks **Begin Forensic Analysis**. What happens next is a multi-stage pipeline that runs in about 15 seconds.

### The Full Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                          USER                                   │
│                                                                 │
│  1. Upload documents:  Denial Letter + EOB + Medical Bill       │
│  2. Answer 2 questions: Plan type?  ERISA or Fully Insured?     │
│  3. Click: Begin Forensic Analysis                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 1 — DOCUMENT INTAKE                     │
│                                                                 │
│  Each PDF is opened and text is extracted.                      │
│  Digital PDFs → direct text extraction                         │
│  Scanned PDFs / Images → flagged for client-side OCR           │
│                                                                 │
│  Three documents are stitched into ONE unified record           │
│  using authority rules:                                         │
│    Denial letter  → owns:  claim ID, appeal deadlines           │
│    EOB            → owns:  billing codes, financial amounts     │
│    Medical bill   → owns:  facility name, itemized charges      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 2 — ENTITY EXTRACTION                   │
│                                                                 │
│  Pass 1 — Regex (free, instant):                                │
│    Extracts codes (ICD-10, CPT, CARC, NPI), dates, amounts,    │
│    claim numbers, prior auth status                             │
│                                                                 │
│  Pass 2 — LLM (contextual):                                     │
│    Extracts names, narratives, denial reasons, labeled amounts, │
│    appeal contact info — things regex can't reliably find       │
│                                                                 │
│  Output: A structured ClaimObject with every field populated   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 3 — ORCHESTRATED ANALYSIS               │
│                                                                 │
│  Pre-step: Root cause is classified FIRST so the regulation     │
│  agent knows what laws to pull (e.g. CMS coverage database     │
│  is only needed for medical necessity denials).                 │
│                                                                 │
│  Then three agents run in PARALLEL:                             │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  CODE LOOKUP    │  │  REGULATION     │  │  STATE RULES    │ │
│  │  AGENT          │  │  AGENT          │  │  AGENT          │ │
│  │                 │  │                 │  │                 │ │
│  │ Looks up every  │  │ Fetches the     │  │ Gets the state  │ │
│  │ code live:      │  │ exact federal   │  │ DOI contact,    │ │
│  │  • ICD-10 →CMS  │  │ laws that apply:│  │ external review │ │
│  │  • CPT   →CMS   │  │  • ERISA plans →│  │ process, and    │ │
│  │  • CARC  →WPC   │  │    DOL §503     │  │ whether the     │ │
│  │  • RARC  →WPC   │  │  • ACA plans → │  │ state DOI or    │ │
│  │  • NPI   →NPPES │  │    §2719/eCFR   │  │ federal ERISA   │ │
│  │ (web fallback   │  │  • Medicaid →   │  │ rules govern    │ │
│  │  for unfound)   │  │    42 CFR 431   │  │ this claim      │ │
│  │                 │  │  • Med necessity│  │                 │ │
│  │                 │  │    → CMS NCD DB │  │                 │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           └───────────────────┬┴───────────────────┘          │
│                               │                                 │
│                               ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  ANALYSIS AGENT (sequential)            │   │
│  │                                                         │   │
│  │  • Root cause:    Why was this denied? (6 categories)  │   │
│  │  • Completeness:  Did the denial letter meet ACA/ERISA  │   │
│  │                   required elements?                    │   │
│  │  • Deadlines:     When must the appeal be filed?        │   │
│  │  • Probability:   How likely is the appeal to succeed?  │   │
│  │  • Severity:      Urgent / Time-Sensitive / Routine     │   │
│  │  • Assumptions:   What the system assumed, with impact  │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 4 — OUTPUT GENERATION                   │
│                                                                 │
│  LLM takes the enriched claim + analysis and generates:        │
│                                                                 │
│    Plain-English summary   →  What happened, in plain English  │
│    Action checklist        →  Numbered steps + legal "why"     │
│    Appeal letter           →  Formal letter with citations     │
│    Provider message        →  Request to billing office        │
│    Insurer message         →  Message to member services       │
│    Provider brief          →  One-pager for treating physician  │
│    Routing card            →  ERISA vs. state DOI guidance     │
│                                                                 │
│  All outputs are cached in the browser so navigating between   │
│  pages is instant — no repeat LLM calls.                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 5 — RESULTS TO USER                     │
│                                                                 │
│  Action Plan dashboard:                                         │
│    • Denial summary with key points                            │
│    • Approval probability gauge                                 │
│    • Recovery roadmap (prioritized steps)                      │
│    • Critical deadlines with one-click calendar (.ics) export  │
│    • Denial notice completeness checklist                       │
│    • Regulatory routing card (who to contact)                  │
│    • Bill breakdown (billed / paid / denied)                    │
│                                                                 │
│  Appeal Drafting:                                               │
│    • Ready-to-send appeal letter                               │
│    • Provider and insurer messages                              │
│    • PDF download                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Orchestration

```
                        ┌──────────────────┐
                        │   ORCHESTRATOR   │
                        └────────┬─────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │  Stage 0: Pre-classify   │
                    │  root cause (Why denied?)│
                    │  → so regulation agent  │
                    │    knows what to fetch  │
                    └────────────┬─────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            │                    │                    │
     ┌──────▼──────┐     ┌───────▼──────┐    ┌───────▼──────┐
     │ CODE LOOKUP │     │  REGULATION  │    │ STATE RULES  │
     │   AGENT     │     │    AGENT     │    │    AGENT     │
     │             │     │              │    │              │
     │ Live APIs:  │     │ Live APIs:   │    │ Live data:   │
     │ CMS ICD-10  │     │ eCFR.gov     │    │ State DOI    │
     │ CMS HCPCS   │     │ DOL ERISA    │    │ contacts     │
     │ NPPES NPI   │     │ ACA §2719    │    │ (50 states)  │
     │ WPC CARC/   │     │ CMS Coverage │    │              │
     │ RARC tables │     │ Database     │    │              │
     └──────┬──────┘     └───────┬──────┘    └───────┬──────┘
            │     (all 3 run simultaneously)          │
            └────────────────────┬────────────────────┘
                                 │  enriched ClaimObject
                    ┌────────────▼─────────────┐
                    │   Stage 2: ANALYSIS      │
                    │   AGENT (sequential)     │
                    │                          │
                    │  • Root cause (final)    │
                    │  • Deadlines             │
                    │  • Completeness          │
                    │  • Probability           │
                    │  • Severity triage       │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   OUTPUT AGENT           │
                    │   (LLM: Groq → Gemini)   │
                    │                          │
                    │  Generates all letters,  │
                    │  summaries, checklists   │
                    └──────────────────────────┘
```

---

## Where Data Comes From

The system never uses a local knowledge base for regulatory or code data. Everything is fetched live from authoritative sources at the time of analysis.

| What | Source | Why live? |
|------|--------|-----------|
| ICD-10 diagnosis codes | CMS / NLM ICD-10-CM API | Codes update annually |
| CPT / HCPCS procedure codes | CMS / NLM HCPCS API | AMA updates quarterly |
| CARC / RARC denial codes | WPC reference table (local) | No public API exists |
| Provider (NPI) lookup | NPPES NPI Registry API | Provider data changes |
| Federal regulations (ERISA, ACA, Medicaid) | eCFR.gov API | Regulations change |
| ERISA §503 appeal rules | DOL EBSA reference | Plan-specific rules |
| ACA §2719 internal/external review | eCFR 45 CFR §147.136 | Key appeal timelines |
| Medicaid fair hearing rules | eCFR 42 CFR §431.220 | State variation exists |
| CMS National Coverage Determinations | CMS Coverage Database | Med-necessity denials only |
| State DOI contacts | Static JSON (50 states) | Rarely changes |
| Unfound codes | Google Custom Search | Last-resort fallback |

---

## How Results Are Stitched Together

Each piece of information collected across the three parallel agents is merged into a single enrichment object that the Analysis Agent and Output Agent then consume:

```
Code Lookup results    ─┐
                         ├──▶  Enrichment Dict  ──▶  Analysis Agent
Regulation results     ─┤                       ──▶  Output Agent (LLM)
                         │                       ──▶  Frontend dashboard
State Rules results    ─┘
```

**Code enrichment** adds plain-English descriptions, common fixes, and source citations to every code found in the documents — the LLM uses these when writing the appeal letter so it can say "code CO-197 means prior authorization was not obtained" rather than just quoting the code.

**Regulation enrichment** determines the exact appeal process steps, deadlines, and whether external review is available. An ERISA plan has a 60-day minimum internal appeal window; an ACA marketplace plan has 180 days. These are not hardcoded — they come from the live regulation text.

**State rules enrichment** determines the routing: does this claim go to the federal DOL (ERISA), the state Department of Insurance, or a Medicaid agency? It pulls the correct contact, complaint URL, and external review process for that state.

The Analysis Agent then uses all of this — plus the ClaimObject — to produce quantified outputs: a 0–100% probability score, exact deadline dates, and a severity flag. These flow into the Output Agent which combines everything into human-readable content.

---

## Features

### Document Processing
- Upload up to 3 documents (PDF, JPG, PNG): Denial Letter, EOB, Medical Bill
- Automatic text extraction from digital PDFs
- Scanned PDF / image detection with client-side OCR fallback
- Multi-document stitching: fields from different documents are merged using authority rules

### Code Analysis
- Live lookup of all ICD-10, CPT, HCPCS, CARC, RARC, and NPI codes found in documents
- Plain-English explanations for every code
- "Common fix" guidance for denial codes
- Source citation (CMS, NLM, NPPES, WPC)

### Regulatory Intelligence
- Automatic ERISA vs. ACA vs. Medicaid routing based on plan type
- Live federal regulation text from eCFR.gov
- CMS National Coverage Determination lookup for medical necessity denials
- Full 50-state DOI contact database

### Analysis & Scoring
- **Root cause classification** — 6 categories: medical necessity, prior auth, coding error, network, eligibility, procedural
- **Denial letter completeness check** — field-by-field audit against ACA §2719 / ERISA §503 required elements
- **Appeal probability score** — 0–100% likelihood of success based on root cause, completeness, and regulatory context
- **Deadline calculation** — exact dates for internal appeal, external review, and expedited review (72h)
- **Severity triage** — Urgent / Time-Sensitive / Routine based on deadline proximity and denied amount
- **Assumptions panel** — explicit list of what the system assumed, with confidence and impact levels

### Generated Outputs
- **Plain-English denial summary** — written at patient reading level with key points
- **Recovery roadmap** — numbered action steps with "why is this required?" expandable explanations
- **Appeal letter** — formal letter to insurer citing applicable regulations and clinical facts
- **Provider message** — request to the billing office (retroactive auth, corrected codes, etc.)
- **Insurer message** — message to member services
- **Provider brief** — one-page summary for the treating physician to support the appeal
- **Regulatory routing card** — which regulator governs this plan, who to contact, exact process steps

### Export
- **PDF download** — appeal letter, provider brief, or denial summary exported as formatted PDF
- **Calendar export (.ics)** — add appeal deadlines directly to Google Calendar, Outlook, or Apple Calendar with 30-day and 7-day reminders

### Infrastructure
- SSE streaming endpoint for progressive rendering (backend ready)
- Session-level output caching — navigating between pages is instant; no LLM calls repeated
- Appeal letter prefetched in background so the Appeal Drafting page opens immediately
- LLM fallback chain: Groq 70B → Groq 8B → Gemini 2.5 Flash → Gemini 2.5 Flash Lite

---

## LLM Usage

The system uses LLMs for three specific tasks only:

1. **Pass 2 extraction** — extracting contextual entities (names, narratives, labeled amounts) that regex cannot reliably find
2. **Root cause disambiguation** — when heuristics are not confident enough (< 75%), an LLM is called to classify the denial reason
3. **Output generation** — writing the appeal letter, summary, action checklist, and provider brief

All code lookups, regulation fetches, deadline calculations, completeness checks, probability estimation, and routing logic are **deterministic** — no LLM involved. This keeps costs low and results auditable.

---

## Limitations

- **No database** — results are only available for the current browser session
- **Scanned document OCR** — requires client-side processing; server does not run OCR
- **Indiana-first** — state-specific resources are most complete for Indiana (IDOI); all 50 states have DOI contacts but regulatory depth varies
- **Not legal advice** — outputs are for informational purposes; patients should consult a patient advocate or attorney for complex cases
