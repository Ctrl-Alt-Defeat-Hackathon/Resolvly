"""
Multi-agent architecture — specialized agents for enrichment and analysis.

Week 2: Code Lookup Agent
Week 3: Orchestrator, Regulation Agent, State Rules Agent, Analysis Agent
"""
from agents.code_lookup_agent import run_code_lookup_agent, CodeLookupResult

__all__ = [
    "run_code_lookup_agent",
    "CodeLookupResult",
]
