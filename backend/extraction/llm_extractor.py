# TODO Week 2: LLM-Powered Extraction (Pass 2)
# Uses Gemini 2.5 Flash with structured output to extract entities requiring context
# (denial narratives, provider names, plan provisions) that regex cannot reliably capture.
# Input: raw text + Pass 1 results
# Output: enriched ClaimObject with higher confidence per-field scores
