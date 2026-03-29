/**
 * Parse currency from JSON / extraction (often string "$1,234.56" or "96.00").
 * Returns null only when missing or unparseable — never guess a demo default.
 */
export function parseMoney(v: unknown): number | null {
  if (v == null) return null
  if (typeof v === 'number' && Number.isFinite(v)) return v
  if (typeof v === 'string') {
    const t = v.replace(/[$,\s]/g, '').trim()
    if (t === '') return null
    const n = Number(t)
    return Number.isFinite(n) ? n : null
  }
  return null
}
