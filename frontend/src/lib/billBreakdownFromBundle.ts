/**
 * Derive bill-breakdown line items and denial cards from stored analyze results.
 * Claim schema has aggregate financials + code lists (no true EOB line-level dollars).
 */
import { parseMoney } from './parseMoney'

export type LineItemCodeType = 'CPT' | 'HCPCS' | 'ICD-10' | 'CARC'

export interface BillLineItem {
  id: string
  code: string
  codeType: LineItemCodeType
  description: string
  plainEnglish: string
  billed: number
  allowed: number | null
  planPaid: number
  denied: number
  patientOwe: number
  denialReason: string | null
  fixable: boolean
  fixSuggestion: string | null
}

export interface EnrichmentCodeEntry {
  code?: string
  code_type?: string
  description?: string
  plain_english?: string
  common_fix?: string
  source?: string
  source_url?: string
  found?: boolean
}

export interface DenialCodeCard {
  raw: string
  kind: 'carc' | 'rarc'
  title: string
  description: string
  plainEnglish: string
  commonFix: string
  isPrimary: boolean
}

function fmtDate(v: unknown): string {
  if (v == null) return '—'
  const s = String(v)
  const d = new Date(s.length === 10 ? `${s}T12:00:00` : s)
  if (Number.isNaN(d.getTime())) return s
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
}

export function buildLineItemsFromClaim(
  claim: Record<string, unknown>,
  enrichmentCodes: Record<string, EnrichmentCodeEntry>,
  analysis: Record<string, unknown>
): BillLineItem[] {
  const service = (claim.service_billing ?? {}) as Record<string, unknown>
  const fin = (claim.financial ?? {}) as Record<string, unknown>
  const denial = (claim.denial_reason ?? {}) as Record<string, unknown>
  const rootCause = (analysis.root_cause ?? {}) as Record<string, unknown>

  const cpts = (service.cpt_procedure_codes as string[]) ?? []
  const hcpcs = (service.hcpcs_codes as string[]) ?? []
  const icds = (service.icd10_diagnosis_codes as string[]) ?? []
  const carcs = (denial.carc_codes as string[]) ?? []

  const billed = parseMoney(fin.billed_amount) ?? 0
  const allowed = parseMoney(fin.allowed_amount)
  const planPaid = parseMoney(fin.insurer_paid_amount) ?? 0
  const denied = parseMoney(fin.denied_amount) ?? 0
  const copay = parseMoney(fin.copay_amount) ?? 0
  const patientResp = parseMoney(fin.patient_responsibility_total) ?? copay

  const procDesc = String(service.procedure_description || '').trim() || 'Claimed services'
  const denialNarrative = denial.denial_reason_narrative ? String(denial.denial_reason_narrative) : null

  const descFor = (key: string, fallback: string) =>
    String(enrichmentCodes[key]?.description || fallback)
  const plainFor = (key: string, desc: string) =>
    String(enrichmentCodes[key]?.plain_english || desc)
  const fixFor = (key: string): string | null => {
    const f = enrichmentCodes[key]?.common_fix
    return f ? String(f) : null
  }

  const items: BillLineItem[] = []
  let n = 0
  const nid = () => String(++n)

  const procList = [
    ...cpts.map(code => ({ raw: code, kind: 'cpt' as const })),
    ...hcpcs.map(code => ({ raw: code, kind: 'hcpcs' as const })),
  ]
  const primaryRows = Math.max(1, procList.length)

  const splitBilled = primaryRows > 0 ? billed / primaryRows : billed
  const splitPlan = primaryRows > 0 ? planPaid / primaryRows : planPaid

  if (procList.length === 0) {
    items.push({
      id: nid(),
      code: 'Claim total',
      codeType: 'CPT',
      description: procDesc,
      plainEnglish: procDesc,
      billed,
      allowed,
      planPaid,
      denied,
      patientOwe: patientResp,
      denialReason: denialNarrative,
      fixable: carcs.length > 0 || rootCause.category === 'prior_authorization',
      fixSuggestion:
        fixFor(carcs[0] || '') ||
        'Work with your provider billing office and your plan appeals unit using the contact info on your EOB.',
    })
  } else {
    procList.forEach((entry, i) => {
      const isFirst = i === 0
      const raw = entry.raw
      if (entry.kind === 'cpt') {
        items.push({
          id: nid(),
          code: `CPT ${raw}`,
          codeType: 'CPT',
          description: descFor(raw, `Procedure ${raw}`),
          plainEnglish: plainFor(raw, descFor(raw, `Procedure code ${raw}`)),
          billed: splitBilled,
          allowed: isFirst ? allowed : null,
          planPaid: splitPlan,
          denied: isFirst ? denied : 0,
          patientOwe: isFirst ? patientResp : 0,
          denialReason: isFirst ? denialNarrative : null,
          fixable: isFirst && (carcs.length > 0 || rootCause.category === 'prior_authorization'),
          fixSuggestion: isFirst ? fixFor(carcs[0] || '') || null : null,
        })
      } else {
        items.push({
          id: nid(),
          code: `HCPCS ${raw}`,
          codeType: 'HCPCS',
          description: descFor(raw, `Supply or service ${raw}`),
          plainEnglish: plainFor(raw, descFor(raw, `HCPCS code ${raw}`)),
          billed: splitBilled,
          allowed: isFirst ? allowed : null,
          planPaid: splitPlan,
          denied: isFirst ? denied : 0,
          patientOwe: isFirst ? patientResp : 0,
          denialReason: isFirst ? denialNarrative : null,
          fixable: isFirst && carcs.length > 0,
          fixSuggestion: isFirst ? fixFor(carcs[0] || '') || null : null,
        })
      }
    })
  }

  icds.forEach(raw => {
    items.push({
      id: nid(),
      code: `ICD-10 ${raw}`,
      codeType: 'ICD-10',
      description: descFor(raw, `Diagnosis ${raw}`),
      plainEnglish: plainFor(raw, 'Diagnosis code associated with this claim.'),
      billed: 0,
      allowed: 0,
      planPaid: 0,
      denied: 0,
      patientOwe: 0,
      denialReason: null,
      fixable: false,
      fixSuggestion: null,
    })
  })

  carcs.forEach(raw => {
    items.push({
      id: nid(),
      code: `CARC ${raw}`,
      codeType: 'CARC',
      description: descFor(raw, 'Claim adjustment reason'),
      plainEnglish: plainFor(raw, descFor(raw, 'Reason the plan adjusted or denied part of this claim.')),
      billed: 0,
      allowed: 0,
      planPaid: 0,
      denied: 0,
      patientOwe: 0,
      denialReason: denialNarrative,
      fixable: Boolean(fixFor(raw)),
      fixSuggestion: fixFor(raw),
    })
  })

  return items
}

export function buildDenialCards(
  claim: Record<string, unknown>,
  enrichmentCodes: Record<string, EnrichmentCodeEntry>
): DenialCodeCard[] {
  const denial = (claim.denial_reason ?? {}) as Record<string, unknown>
  const carcs = (denial.carc_codes as string[]) ?? []
  const rarcs = (denial.rarc_codes as string[]) ?? []
  const cards: DenialCodeCard[] = []

  carcs.forEach((raw, i) => {
    const e = enrichmentCodes[raw]
    cards.push({
      raw,
      kind: 'carc',
      title: e?.description ? String(e.description) : `CARC ${raw}`,
      description: e?.description ? String(e.description) : 'Description will load from code lookup.',
      plainEnglish: e?.plain_english ? String(e.plain_english) : '',
      commonFix: e?.common_fix ? String(e.common_fix) : '',
      isPrimary: i === 0,
    })
  })

  rarcs.forEach((raw, i) => {
    const e = enrichmentCodes[raw]
    cards.push({
      raw,
      kind: 'rarc',
      title: e?.description ? String(e.description) : `RARC ${raw}`,
      description: e?.description ? String(e.description) : 'Remittance advice remark.',
      plainEnglish: e?.plain_english ? String(e.plain_english) : '',
      commonFix: '',
      isPrimary: carcs.length === 0 && i === 0,
    })
  })

  return cards
}

/** Pretty-print CARC for UI (extracted values are often "15" or "CO-15"). */
export function formatCarcLabel(raw: string): string {
  const s = raw.trim()
  if (!s) return '—'
  if (/^(CO|PR|OA|PI|CR)[-\s]?\d+$/i.test(s)) return s.toUpperCase().replace(/\s+/g, '-')
  if (/^\d+$/.test(s)) return `CO-${s}`
  return s
}

export function claimMetaFromBundle(
  claim: Record<string, unknown>,
  fallback: { id: string; patient: string; provider: string; insurer: string; dateOfService: string; dateOfDenial: string }
) {
  const ident = (claim.identification ?? {}) as Record<string, unknown>
  const pp = (claim.patient_provider ?? {}) as Record<string, unknown>
  return {
    id: ident.claim_reference_number ? `#${String(ident.claim_reference_number)}` : fallback.id,
    patient: (pp.patient_full_name as string) || fallback.patient,
    provider: (pp.treating_provider_name as string) || fallback.provider,
    insurer: fallback.insurer,
    dateOfService: fmtDate(ident.date_of_service) || fallback.dateOfService,
    dateOfDenial: fmtDate(ident.date_of_denial) || fallback.dateOfDenial,
  }
}
