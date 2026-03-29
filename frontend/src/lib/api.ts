const API = '/api/v1'

async function handleJson<T>(res: Response): Promise<T> {
  const text = await res.text()
  if (!res.ok) {
    throw new Error(text || res.statusText || `HTTP ${res.status}`)
  }
  return text ? (JSON.parse(text) as T) : ({} as T)
}

export async function uploadDocuments(files: File[]) {
  const fd = new FormData()
  for (const f of files) {
    fd.append('files', f)
  }
  const res = await fetch(`${API}/documents/upload`, { method: 'POST', body: fd })
  return handleJson<{
    upload_id: string
    documents: Array<{
      doc_id: string
      filename: string
      text_extracted: string
      ocr_used: boolean
      ocr_confidence: number | null
      page_count: number
    }>
  }>(res)
}

export async function extractEntities(body: {
  upload_id: string
  documents: Array<{ doc_id: string; text_extracted: string }>
  plan_context: Record<string, unknown>
}) {
  const res = await fetch(`${API}/documents/extract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  })
  return handleJson<{
    claim_object: Record<string, unknown>
    extraction_confidence: { overall: number; per_field: Record<string, number> }
    warnings: string[]
  }>(res)
}

export async function analyzeClaim(claim_object: Record<string, unknown>, plan_context: Record<string, unknown>) {
  const res = await fetch(`${API}/claims/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ claim_object, plan_context }),
  })
  return handleJson<{
    enrichment: Record<string, unknown>
    analysis: Record<string, unknown>
    sources: unknown[]
    claim_object: Record<string, unknown>
  }>(res)
}

export async function wizardPlanType(body: {
  source: string
  employer_plan_type?: string
  state: string
}) {
  const res = await fetch(`${API}/wizard/plan-type`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  })
  return handleJson<Record<string, unknown>>(res)
}

export async function postActionChecklist(
  claim_object: Record<string, unknown>,
  analysis: Record<string, unknown>,
  enrichment: Record<string, unknown>
) {
  const res = await fetch(`${API}/outputs/action-checklist`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ claim_object, analysis, enrichment }),
  })
  return handleJson<{ steps: Array<Record<string, unknown>>; total_steps: number }>(res)
}

export async function postAppealLetter(
  claim_object: Record<string, unknown>,
  analysis: Record<string, unknown>,
  enrichment: Record<string, unknown>,
  patient_info: Record<string, string> = {}
) {
  const res = await fetch(`${API}/outputs/appeal-letter`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ claim_object, analysis, enrichment, patient_info }),
  })
  return handleJson<{
    appeal_letter?: string
    provider_message?: string
    insurer_message?: string
    legal_citations?: unknown[]
  }>(res)
}

export async function postDeadlines(claim_object: Record<string, unknown>, analysis: Record<string, unknown>) {
  const res = await fetch(`${API}/outputs/deadlines`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ claim_object, analysis }),
  })
  return handleJson<{
    deadlines: Array<{ type: string; date?: string; ics_data?: string; source_law?: string }>
  }>(res)
}

export async function postExportIcs(body: {
  event_title: string
  event_date: string
  description?: string
  reminder_days_before?: number[]
}) {
  const res = await fetch(`${API}/export/ics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.blob()
}

export async function postExportPdf(body: { content: string; format: string; title?: string }) {
  const res = await fetch(`${API}/export/pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.blob()
}
