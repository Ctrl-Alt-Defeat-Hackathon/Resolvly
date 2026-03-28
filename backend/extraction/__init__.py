"""
Entity extraction pipeline — two-pass hybrid extraction.

Pass 1: Deterministic regex extraction (regex_extractor)
Pass 2: LLM-powered extraction via Gemini (llm_extractor)
Multi-doc: Document stitcher for merging multiple document extractions
"""
from extraction.regex_extractor import extract_pass1
from extraction.llm_extractor import extract_pass2
from extraction.document_stitcher import stitch_documents, classify_document
from extraction.schema import ClaimObject, ExtractionConfidence, PlanContext

__all__ = [
    "extract_pass1",
    "extract_pass2",
    "stitch_documents",
    "classify_document",
    "ClaimObject",
    "ExtractionConfidence",
    "PlanContext",
]
