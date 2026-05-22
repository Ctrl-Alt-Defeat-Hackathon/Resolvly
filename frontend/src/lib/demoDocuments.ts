export type DocKind = 'eob' | 'denial' | 'medical_bill'

export type DemoCaseId = 'default' | 'fontaine' | 'nguyen'

export const DEMO_MODE_SESSION_KEY = 'resolvly_demo_mode'
export const DEMO_CASE_SESSION_KEY = 'resolvly_demo_case'
export const DEMO_OFFER_SESSION_KEY = 'resolvly_demo_offer_answered'

const DEMO_FILE_NAMES: Record<DocKind, string> = {
  denial: 'denial.pdf',
  eob: 'eob.pdf',
  medical_bill: 'medical-bill.pdf',
}

export const DEMO_CASES: Array<{
  id: DemoCaseId
  label: string
  subtitle: string
}> = [
  { id: 'default', label: 'Demo case 1', subtitle: 'Standard denial + EOB + bill' },
  { id: 'fontaine', label: 'Demo case 2', subtitle: 'Fontaine sample documents' },
  { id: 'nguyen', label: 'Demo case 3', subtitle: 'Nguyen sample documents' },
]

export function demoAssetPath(caseId: DemoCaseId, kind: DocKind): string {
  const base = (import.meta.env.BASE_URL ?? '/').replace(/\/$/, '')
  return `${base}/demo-documents/case-${caseId}/${DEMO_FILE_NAMES[kind]}`
}

export async function fetchDemoFile(caseId: DemoCaseId, kind: DocKind): Promise<File> {
  const url = demoAssetPath(caseId, kind)
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`Demo file not found (${kind}). Add PDFs under public/demo-documents/case-${caseId}/`)
  }
  const blob = await res.blob()
  const name = DEMO_FILE_NAMES[kind]
  return new File([blob], name, { type: blob.type || 'application/pdf' })
}

export async function fetchDemoCaseFiles(caseId: DemoCaseId): Promise<Record<DocKind, File>> {
  const kinds: DocKind[] = ['denial', 'eob', 'medical_bill']
  const entries = await Promise.all(
    kinds.map(async kind => [kind, await fetchDemoFile(caseId, kind)] as const),
  )
  return Object.fromEntries(entries) as Record<DocKind, File>
}
