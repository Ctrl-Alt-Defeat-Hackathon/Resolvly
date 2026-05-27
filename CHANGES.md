# Backend Architecture Changes — Commit `442a4ed`

**Author:** Athish49 (agr@iu.edu)
**Date:** May 22, 2026
**Branch:** `backend_architecture_v2` → merged via PR #28
**Summary:** 31 files changed, +2739 / -591 lines

---

## Overview

This commit is a major architectural overhaul of the extraction pipeline and agent orchestration layer. The changes introduce:

- Feature-based confidence scoring per extracted field (replacing a coarse 3-bucket step function)
- Per-page OCR detection and a server-side OCR fallback endpoint
- Financial reconciliation checks on extracted EOB figures
- A validation loop that flags unresolved medical codes before appeal letter generation
- Structured `ClaimGap` error responses when critical claim fields are missing
- Weighted document classification replacing fragile keyword counting
- Per-agent timeouts and graceful failure handling in the orchestrator
- Richer state appeal rules data and expanded CARC/RARC code coverage

---

## New Files

### `backend/api/routes/ocr.py`

**`POST /api/v1/documents/ocr/page`** — server-side OCR fallback.

- Accepts a single-page PNG/JPEG image upload.
- Runs `pytesseract.image_to_data()` and returns `text`, `confidence` (0–1), and `engine: "pytesseract"`.
- Returns **HTTP 501** if `pytesseract` is not installed, so the client falls back to Tesseract.js.
- Clients call this when Tesseract.js returns average confidence < 0.6 or crashes.

---

### `backend/api/errors.py`

**Structured `ClaimGap` error types** for the analysis pipeline.

- `ClaimGapField` — describes a single missing field with a `display_label`, `where_to_look` hint, and `regulation_basis` reference.
- `ClaimGap` — the 422 response body, containing a list of missing fields and a `can_proceed_partial` flag.
- `check_blocking_fields(claim)` — inspects a `ClaimObject` and returns `ClaimGap | None`.
- Four blocking fields are defined:
  | Field | Regulation Basis |
  |---|---|
  | `date_of_denial` | 29 C.F.R. §2560.503-1(g)(1)(i) / ACA §2719 |
  | `denial_reason_narrative` | 29 C.F.R. §2560.503-1(g)(1)(ii) |
  | `claim_reference_number` | Insurer/regulatory correspondence |
  | `regulation_type` (ERISA vs. State) | Determines applicable deadlines and rights |
- `can_proceed_partial` is `True` only when the sole missing field is `regulation_type` (the pipeline can still produce deadlines for both ERISA and state paths).

---

### `backend/analysis/financial_reconciliation.py`

**Financial consistency checker** (§5.2).

Verifies three financial equations extracted from the EOB, flagging any discrepancies as assumptions in the appeal analysis:

| Equation | Tolerance |
|---|---|
| `patient_responsibility_total ≈ copay + coinsurance + deductible` | $1.00 |
| `insurer_paid + patient_responsibility ≈ allowed_amount` | $1.00 |
| `implied_adjustment = billed - allowed - denied` must be ≥ 0 | $1.00 |

- Returns a `FinancialReconciliationResult` with `reconciled`, `discrepancies`, `assumptions`, and `implied_adjustment`.
- Each discrepancy is appended as an assumption with a confidence and impact rating.

---

### `backend/analysis/validation_loop.py`

**Post-code-lookup quality check** (§5.1).

- Receives the `CodeLookupResult` after the Code Lookup Agent completes.
- Counts codes that could not be resolved against CMS/NLM/NPPES authorities.
- Emits a per-code assumption for every unresolved code with a plain-English hint (e.g., "Verify the ICD-10-CM code with the treating provider's medical records.").
- Sets `requires_review = True` when the unresolved rate exceeds **50%** and prepends a high-impact assumption.
- Supported code types with tailored hints: `icd10`, `cpt`, `hcpcs`, `carc`, `rarc`, `npi`.

---

### `backend/extraction/confidence_scorer.py`

**Feature-based per-field confidence scoring** (§6).

Replaces the coarse 3-bucket step function (`0.7 regex / 0.9 LLM / 1.0 both`) with scores derived from *how* each value was extracted:

| Score | Meaning |
|---|---|
| 0.97 | Cross-validated: Pass 1 and Pass 2 agree |
| 0.92–0.93 | Verbatim labeled pattern fired (e.g., `"Date of Denial: …"`, explicit `"CARC: 50"` form) |
| 0.85–0.90 | Well-structured labeled pattern or LLM extraction |
| 0.75–0.82 | Reliable but less specific pattern (IDs, codes) |
| 0.50 | Disputed (Pass 1 ≠ Pass 2) or positional currency fallback |
| 0.0 | Field not found |

Key functions:
- `compute_pass1_field_confidence(field_name, value, raw)` — per-field confidence from regex extraction quality signals.
- `cross_validate_field(field_name, p1_value, p2_value)` — compares Pass 1 and Pass 2 values; returns `(confidence, agreed, disputed_values)`.
- `_normalize_for_compare()` — normalizes dates, amounts, and strings for equality comparison across passes.

---

### `backend/data/state_appeal_rules.json`

New dataset file containing state-specific appeal rules, deadlines, and Department of Insurance (DOI) contact information used by the State Rules Agent.

---

## Modified Files

### `backend/extraction/schema.py`

Two new model classes and additions to `ClaimObject`:

**`FieldProvenance`** — tracks extraction origin for each field:
```
value, source_doc_id, extractor (regex|llm|user|missing|unknown),
confidence (0.0–1.0), source_url, disputed_values
```
`disputed_values` is populated `[p1_value, p2_value]` when Pass 1 and Pass 2 disagree.

**`StateDeadlines`** — replaces the unstructured `dict[str, str]` for state deadlines:
```
internal_appeal_days, external_review_days, external_review_authority,
expedited_hours, regulation_basis, source_url, last_verified, note
```
Includes `StateDeadlines.from_legacy_dict()` for backward compatibility.

**`ClaimObject` additions:**
- `provenance: dict[str, FieldProvenance]` — per-field extraction provenance map.
- `regulation_type_source: Literal["user", "extracted", "defaulted"]` — how `regulation_type` was determined.
- `unverified_codes: list[str]` — codes excluded from appeal letter citations.
- `carc_codes_with_group: dict[str, str]` — maps CARC codes to their EOB group prefix (CO, PR, OA, etc.) for responsible-party inference.

---

### `backend/extraction/pdf_extractor.py`

**Per-page OCR detection** (v2 improvements):

- Pages are individually classified as scanned when `text_chars < 30` AND the page contains embedded images (previously a whole-document threshold).
- New `PageMeta` dataclass: `page_number`, `text_chars`, `has_images`, `is_scanned`.
- `ExtractionResult` gains: `pages_meta`, `tables`, `scanned_page_numbers`, `has_mixed_content`.
- `DocumentType` now supports `pdf_mixed` for documents with both digital and scanned pages.
- Structured table data is preserved in `ExtractionResult.tables` instead of being flattened into text.
- `needs_client_ocr` is set to `True` only for pages that are actually scanned (not the entire document).

---

### `backend/extraction/document_stitcher.py` (v2)

**Complete rewrite of the document classifier:**

- Old: keyword frequency count across flat lists.
- New: **weighted feature-scoring** using compiled regexes with per-rule weights (2–5 points).
- Classification confidence = `(winner_score - runner_up_score) / winner_score`.
- Documents below the 0.30 confidence threshold are classified as `requires_review` instead of silently assigned to the wrong type.
- `classify_document()` is preserved as a backward-compatible wrapper; `classify_document_scored()` returns `(doc_type, confidence)`.

**Quality-ranking within duplicate document types:**
- When multiple docs of the same type are uploaded, they are now scored by quality (content length, presence of denial date, CARC codes, financial amounts) rather than simply using the first occurrence.

**Claim-ID consistency check (`_check_claim_id_consistency`):**
- Warns when documents contain conflicting `claim_reference_number` values — surfaces a human-readable warning before merge.

**Merge improvements:**
- `_merge_value` now also handles `dict` merging (`{**existing, **new}`).
- `carc_code_groups` added to the EOB field authority list.

---

### `backend/api/routes/extract.py`

**Provenance pipeline integrated into extraction flow** (§5.4):

Three new functions wired into the extraction endpoint:

1. **`_populate_provenance_pass1(claim, raw, primary_doc_id)`** — after Pass 1 (regex), writes a `FieldProvenance` entry for each tracked field using `compute_pass1_field_confidence()`.

2. **`_update_provenance_llm(claim, pass2)`** — after Pass 2 (LLM), upgrades provenance for fields where LLM confidence exceeds the existing regex confidence.

3. **`_cross_validate_and_finalize_provenance(claim, raw, pass2)`** — compares Pass 1 and Pass 2 values for 7 key fields:
   - Agreed values → confidence upgraded to **0.97** (cross-validated).
   - Disagreed values → confidence set to **0.50**, `disputed_values` populated.
   - Returns a list of disputed field names (used to append warnings).

**`_confidence_from_results` rewrite:**
- Critical fields (`date_of_denial`, `carc_codes`, `denial_reason_narrative`) now weighted **2×** in the overall score.
- Uses provenance-based confidence first; falls back to LLM-reported `<field>_confidence` keys; then falls back to legacy step function.
- Overall score is a weighted average instead of a simple mean.

---

### `backend/agents/orchestrator.py`

**Per-agent timeouts and graceful failure handling:**

| Agent | Timeout |
|---|---|
| `code_lookup_agent` | 15 s |
| `regulation_agent` | 20 s |
| `state_rules_agent` | 20 s |
| `analysis_agent` | 30 s |

- `_with_timeout(coro, timeout_s, agent_name)` wraps each agent call with `asyncio.wait_for`.
- `asyncio.gather` now uses `return_exceptions=True` — one failing agent no longer kills the entire pipeline.
- `_unpack_agent_outcomes()` substitutes empty defaults for failed agents and records status.
- `OrchestratorResult` gains three new fields: `errors: list[str]`, `agent_status: dict[str, str]` (`"ok" | "timeout" | "error"`), `llm_available: bool`.
- `stream_orchestrator` receives the same timeout and error-handling treatment for its per-task streaming path.
- `state_deadlines` now serialized via `.model_dump()` (was a raw dict).
- `analysis_agent` now receives `code_lookup_result` to avoid a second code classification call.

---

### `backend/agents/analysis_agent.py`

Two new analysis steps added to the pipeline:

- **Step 7** — `check_financial_reconciliation(claim)`: runs after existing analysis steps; appends discrepancy assumptions.
- **Step 8** — `run_validation_loop(claim, code_lookup_result)`: uses the code result passed from the orchestrator; appends unresolved-code assumptions.
- `AnalysisResult` gains `financial_reconciliation: dict` and `requires_review: bool`.
- Accepts optional `code_lookup_result: CodeLookupResult` parameter (no re-fetch needed).

---

### `backend/extraction/regex_extractor.py`

- CARC group prefix parsing improved — now captures the group prefix (CO, PR, OA, PI, CR) separately from the numeric code.
- `carc_code_groups` dict added to the raw output: maps code → group prefix.

---

### `backend/extraction/llm_extractor.py`

- LLM prompt updated to request per-field confidence values as `<field>_confidence` keys alongside extracted values.
- Extract route can now consume these directly in `_confidence_from_results`.

---

### `backend/tools/carc_rarc_lookup.py`

Expanded CARC code table with 10 new entries:

| Code | Description |
|---|---|
| 7 | Procedure inconsistent with patient gender |
| 8 | Procedure inconsistent with provider specialty/taxonomy |
| 12 | Diagnosis inconsistent with patient gender |
| 13 | Date of death precedes date of service |
| 14 | Date of birth follows date of service |
| 17 | Procedure not paid separately (bundling) |
| 19 | Work-related injury — Workers' Compensation applies |
| 26 | Expenses incurred prior to coverage effective date |
| 31 | Patient cannot be identified as insured |
| 35 | Lifetime benefit maximum reached |

Each entry includes `description`, `plain_english` (patient-facing language), and `common_fix`.

---

### `backend/agents/regulation_agent.py` / `state_rules_agent.py`

- `StateRulesEnrichment.state_deadlines` type changed from `dict[str, str]` to `StateDeadlines` (the new structured model).
- `state_rules_agent` updated to load data from `backend/data/state_appeal_rules.json`.
- Regulation agent expanded with additional regulation references and ERISA/ACA cross-linking.

---

### `backend/analysis/` (existing files)

| File | Change |
|---|---|
| `completeness_checker.py` | Aligned field names with updated `ClaimObject` schema |
| `deadline_calculator.py` | Uses `StateDeadlines` model instead of raw dict |
| `probability_estimator.py` | Updated scoring to incorporate `requires_review` flag |
| `root_cause_classifier.py` | Minor refinements to category mapping |
| `severity_triage.py` | Updated to use provenance confidence in severity scoring |

---

### `backend/api/routes/wizard.py`

- Sets `regulation_type_source = "user"` when the wizard completes — surfaced in the assumptions panel.
- Extended wizard flow handles more plan-type edge cases.

### `backend/api/routes/analyze.py`, `outputs.py`, `upload.py`

- Minor additions to wire in `agent_status`, `llm_available`, and `errors` fields from `OrchestratorResult`.

### `backend/main.py`

- OCR router (`/ocr`) registered in the FastAPI app.

### `backend/tools/llm_client.py`

- `is_llm_available()` function added — checks whether an LLM API key is configured or Ollama is reachable; used by the orchestrator to populate `llm_available` in the response.

---

## Workflow Changes Summary

```
Before:                                  After:
-------                                  ------
keyword-count doc classifier             weighted feature-score classifier
                                           + confidence threshold
                                           + quality ranking on duplicates
                                           + claim-ID consistency check

3-bucket confidence (0.7/0.9/1.0)       per-field feature-based confidence
                                           + LLM-reported field confidence
                                           + cross-validation (0.97 agreed / 0.50 disputed)
                                           + FieldProvenance tracking

no financial validation                  FinancialReconciliation (3 equations, $1 tolerance)

no code resolution QA                    ValidationLoop (unresolved rate, requires_review flag)

no blocking field check                  ClaimGap — 422 with actionable guidance per field

no OCR endpoint                          POST /ocr/page (pytesseract, 501 fallback)

whole-document scanned detection         per-page scanned detection + pdf_mixed type

no agent timeouts (failure = crash)      per-agent timeouts + graceful empty defaults
                                           + agent_status in response
```
