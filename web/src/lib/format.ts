const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const usd0 = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

export const money = (cents: number) => usd.format(cents / 100)
export const money0 = (cents: number) => usd0.format(Math.round(cents / 100))

/** "12.50" / "$1,200" -> cents. Returns null for anything unparseable. */
export function toCents(input: string): number | null {
  const n = Number(input.replace(/[$,\s]/g, ''))
  return Number.isFinite(n) && input.trim() !== '' ? Math.round(n * 100) : null
}

export const dollars = (cents: number) => (cents / 100).toFixed(2).replace(/\.00$/, '')

// API dates are YYYY-MM-DD; parse as local dates so they don't shift a day.
const parse = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export const shortDate = (iso: string) => parse(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

export const monthYear = (iso: string) => parse(iso).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

export function daysUntil(iso: string, today = new Date()): number {
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.round((parse(iso).getTime() - t.getTime()) / 86_400_000)
}

/** "just now", "5 min ago", "3 h ago" for an ISO timestamp. */
export function timeAgo(iso: string, now = Date.now()) {
  const min = Math.round((now - new Date(iso).getTime()) / 60_000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min} min ago`
  if (min < 48 * 60) return `${Math.round(min / 60)} h ago`
  return `${Math.round(min / 1440)} days ago`
}

export function ordinal(n: number) {
  const s = ['th', 'st', 'nd', 'rd']
  const v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}
