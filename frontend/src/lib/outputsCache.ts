/**
 * Outputs Cache Layer
 * 
 * Caches LLM-generated outputs in sessionStorage to prevent redundant API calls
 * when navigating between pages. All outputs are deterministic functions of the
 * analysis bundle (claim_object + analysis + enrichment), so we can safely cache
 * them for the session.
 * 
 * Cache invalidation: Automatically invalidates when analysisBundleFingerprint changes
 * (i.e., when a new document is uploaded and analyzed).
 */

import { analysisBundleFingerprint } from './sessionKeys'
import * as api from './api'

const CACHE_PREFIX = 'resolvly_output_cache_'
const CACHE_VERSION_KEY = 'resolvly_output_cache_version'

type CacheKey = 
  | 'summary'
  | 'probability'
  | 'action_checklist'
  | 'appeal_letter'
  | 'provider_brief'
  | 'deadlines'
  | 'assumptions'
  | 'routing_card'
  | 'completeness'

/**
 * Get the current cache version (based on analysis bundle fingerprint).
 * If the fingerprint changes, all cached outputs are invalidated.
 */
function getCurrentCacheVersion(): string {
  const fingerprint = analysisBundleFingerprint()
  const storedVersion = sessionStorage.getItem(CACHE_VERSION_KEY)
  
  // Only clear cache if fingerprint actually changed (not on first initialization)
  if (storedVersion && storedVersion !== fingerprint) {
    // Fingerprint changed - clear all cached outputs
    console.log('[Cache] Analysis bundle changed, clearing cache')
    clearOutputsCache()
    sessionStorage.setItem(CACHE_VERSION_KEY, fingerprint)
  } else if (!storedVersion && fingerprint) {
    // First initialization - set version without clearing
    sessionStorage.setItem(CACHE_VERSION_KEY, fingerprint)
  }
  
  return fingerprint
}

/**
 * Clear all cached outputs (called when analysis bundle changes).
 */
function clearOutputsCache(): void {
  const keys = Object.keys(sessionStorage)
  for (const key of keys) {
    if (key.startsWith(CACHE_PREFIX)) {
      sessionStorage.removeItem(key)
    }
  }
}

/**
 * Get cached output if available and valid.
 */
function getCached<T>(key: CacheKey): T | null {
  try {
    const version = getCurrentCacheVersion() // Ensure cache is valid
    const cacheKey = `${CACHE_PREFIX}${key}`
    const cached = sessionStorage.getItem(cacheKey)
    
    if (cached) {
      console.log(`[Cache] ✓ Cache HIT for ${key} (version: ${version.substring(0, 8)}...)`)
      return JSON.parse(cached) as T
    } else {
      console.log(`[Cache] ✗ Cache MISS for ${key} (version: ${version.substring(0, 8)}...)`)
    }
  } catch (e) {
    console.warn(`[Cache] Failed to read cache for ${key}:`, e)
  }
  return null
}

/**
 * Store output in cache.
 */
function setCached<T>(key: CacheKey, value: T): void {
  try {
    const version = getCurrentCacheVersion() // Ensure cache version is set
    const cacheKey = `${CACHE_PREFIX}${key}`
    sessionStorage.setItem(cacheKey, JSON.stringify(value))
    console.log(`[Cache] ✓ Stored ${key} in cache (version: ${version.substring(0, 8)}...)`)
  } catch (e) {
    console.warn(`[Cache] Failed to cache ${key}:`, e)
  }
}

/**
 * Cached wrapper for postSummary.
 */
export async function getCachedSummary(
  claim_object: Record<string, unknown>,
  analysis: Record<string, unknown>,
  enrichment: Record<string, unknown>
) {
  const cached = getCached<{
    summary_text: string
    reading_level: string
    key_points: string[]
  }>('summary')
  
  if (cached) {
    return cached
  }
  
  const result = await api.postSummary(claim_object, analysis, enrichment)
  setCached('summary', result)
  return result
}

/**
 * Cached wrapper for postProbability.
 */
export async function getCachedProbability(
  claim_object: Record<string, unknown>,
  analysis: Record<string, unknown>,
  enrichment: Record<string, unknown>
) {
  const cached = getCached<{
    score: number
    percentage: string
    interpretation: string
    reasoning: string
    top_recommendation: string
  }>('probability')
  
  if (cached) {
    return cached
  }
  
  const result = await api.postProbability(claim_object, analysis, enrichment)
  setCached('probability', result)
  return result
}

/**
 * Cached wrapper for postActionChecklist.
 */
export async function getCachedActionChecklist(
  claim_object: Record<string, unknown>,
  analysis: Record<string, unknown>,
  enrichment: Record<string, unknown>
) {
  const cached = getCached<{ steps: Array<Record<string, unknown>>; total_steps: number }>('action_checklist')
  
  if (cached) {
    return cached
  }
  
  const result = await api.postActionChecklist(claim_object, analysis, enrichment)
  setCached('action_checklist', result)
  return result
}

/**
 * Cached wrapper for postAppealLetter.
 * Note: patient_info can vary, so we cache by patient_info JSON string.
 */
export async function getCachedAppealLetter(
  claim_object: Record<string, unknown>,
  analysis: Record<string, unknown>,
  enrichment: Record<string, unknown>,
  patient_info: Record<string, string> = {}
) {
  const patientInfoKey = JSON.stringify(patient_info)
  const cacheKey = `appeal_letter_${patientInfoKey}` as CacheKey
  
  const cached = getCached<{
    appeal_letter?: string
    provider_message?: string
    insurer_message?: string
    legal_citations?: unknown[]
  }>(cacheKey)
  
  if (cached) {
    return cached
  }
  
  const result = await api.postAppealLetter(claim_object, analysis, enrichment, patient_info)
  setCached(cacheKey, result)
  return result
}

/**
 * Cached wrapper for postProviderBrief.
 */
export async function getCachedProviderBrief(
  claim_object: Record<string, unknown>,
  analysis: Record<string, unknown>,
  enrichment: Record<string, unknown>
) {
  const cached = getCached<{ brief_text: string; format?: string; pdf_ready?: boolean }>('provider_brief')
  
  if (cached) {
    return cached
  }
  
  const result = await api.postProviderBrief(claim_object, analysis, enrichment)
  setCached('provider_brief', result)
  return result
}

/**
 * Cached wrapper for postDeadlines.
 */
export async function getCachedDeadlines(
  claim_object: Record<string, unknown>,
  analysis: Record<string, unknown>
) {
  const cached = getCached<{
    deadlines: Array<{ type: string; date?: string; ics_data?: string; source_law?: string }>
  }>('deadlines')
  
  if (cached) {
    return cached
  }
  
  const result = await api.postDeadlines(claim_object, analysis)
  setCached('deadlines', result)
  return result
}

/**
 * Cached wrapper for postAssumptionsPanel.
 */
export async function getCachedAssumptions(
  claim_object: Record<string, unknown>,
  analysis: Record<string, unknown>,
  enrichment: Record<string, unknown>
) {
  const cached = getCached<{
    assumptions: Array<{
      assumption: string
      confidence: number
      confidence_percentage: string
      impact: string
      how_to_verify: string
      if_incorrect: string
    }>
    high_impact_count: number
    medium_impact_count: number
    overall_confidence: number
    overall_confidence_percentage: string
    reliability_note: string
  }>('assumptions')
  
  if (cached) {
    return cached
  }
  
  const result = await api.postAssumptionsPanel(claim_object, analysis, enrichment)
  setCached('assumptions', result)
  return result
}

/**
 * Cached wrapper for postRoutingCard.
 */
export async function getCachedRoutingCard(
  claim_object: Record<string, unknown>,
  analysis: Record<string, unknown>,
  enrichment: Record<string, unknown>
) {
  const cached = getCached<Record<string, unknown>>('routing_card')
  
  if (cached) {
    return cached
  }
  
  const result = await api.postRoutingCard(claim_object, analysis, enrichment)
  setCached('routing_card', result)
  return result
}

/**
 * Cached wrapper for postCompletenessReport.
 */
export async function getCachedCompleteness(
  claim_object: Record<string, unknown>,
  analysis: Record<string, unknown>,
  enrichment: Record<string, unknown>
) {
  const cached = getCached<{
    score: number
    score_percentage: string
    regulation_standard: string
    deficient: boolean
    escalation_available: boolean
    escalation_reason: string
    checklist: Array<{
      field: string
      present: boolean
      required_by: string
      why_it_matters: string
      action_if_missing: string
    }>
    present_count: number
    missing_count: number
    summary: string
  }>('completeness')
  
  if (cached) {
    return cached
  }
  
  const result = await api.postCompletenessReport(claim_object, analysis, enrichment)
  setCached('completeness', result)
  return result
}

/**
 * Manually clear all cached outputs (useful for debugging or forced refresh).
 */
export function clearAllOutputsCache(): void {
  clearOutputsCache()
  sessionStorage.removeItem(CACHE_VERSION_KEY)
  console.log('[Cache] All outputs cache cleared')
}
