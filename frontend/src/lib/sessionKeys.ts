/** Session storage keys for claim pipeline + analysis results */

export const STORAGE_KEYS = {
  ANALYSIS_COMPLETE: 'resolvly_analysis_complete',
  CLAIM_OBJECT: 'resolvly_claim_object',
  ANALYSIS: 'resolvly_analysis',
  ENRICHMENT: 'resolvly_enrichment',
  SOURCES: 'resolvly_sources',
  PLAN_CONTEXT: 'resolvly_plan_context',
  WIZARD: 'resolvly_wizard',
  DOC_PROFILE: 'resolvly_doc_profile',
} as const

export type StoredAnalysisBundle = {
  claim_object: Record<string, unknown>
  analysis: Record<string, unknown>
  enrichment: Record<string, unknown>
  sources: unknown[]
  plan_context: Record<string, unknown>
  wizard: Record<string, unknown> | null
}

export function loadAnalysisBundle(): StoredAnalysisBundle | null {
  try {
    const claimRaw = sessionStorage.getItem(STORAGE_KEYS.CLAIM_OBJECT)
    const analysisRaw = sessionStorage.getItem(STORAGE_KEYS.ANALYSIS)
    if (!claimRaw || !analysisRaw) return null
    return {
      claim_object: JSON.parse(claimRaw) as Record<string, unknown>,
      analysis: JSON.parse(analysisRaw) as Record<string, unknown>,
      enrichment: JSON.parse(sessionStorage.getItem(STORAGE_KEYS.ENRICHMENT) || '{}') as Record<string, unknown>,
      sources: JSON.parse(sessionStorage.getItem(STORAGE_KEYS.SOURCES) || '[]') as unknown[],
      plan_context: JSON.parse(sessionStorage.getItem(STORAGE_KEYS.PLAN_CONTEXT) || '{}') as Record<string, unknown>,
      wizard: sessionStorage.getItem(STORAGE_KEYS.WIZARD)
        ? (JSON.parse(sessionStorage.getItem(STORAGE_KEYS.WIZARD)!) as Record<string, unknown>)
        : null,
    }
  } catch {
    return null
  }
}

export function saveAnalysisBundle(bundle: StoredAnalysisBundle): void {
  sessionStorage.setItem(STORAGE_KEYS.CLAIM_OBJECT, JSON.stringify(bundle.claim_object))
  sessionStorage.setItem(STORAGE_KEYS.ANALYSIS, JSON.stringify(bundle.analysis))
  sessionStorage.setItem(STORAGE_KEYS.ENRICHMENT, JSON.stringify(bundle.enrichment))
  sessionStorage.setItem(STORAGE_KEYS.SOURCES, JSON.stringify(bundle.sources))
  sessionStorage.setItem(STORAGE_KEYS.PLAN_CONTEXT, JSON.stringify(bundle.plan_context))
  if (bundle.wizard) {
    sessionStorage.setItem(STORAGE_KEYS.WIZARD, JSON.stringify(bundle.wizard))
  } else {
    sessionStorage.removeItem(STORAGE_KEYS.WIZARD)
  }
}
