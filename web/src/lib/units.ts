// Mirrors backend meal/units.py: canonical units and friendly amounts.

export const UNITS = [
  'lb',
  'oz',
  'g',
  'kg',
  'cup',
  'tbsp',
  'tsp',
  'fl oz',
  'ml',
  'l',
  'pint',
  'quart',
  'gallon',
  'can',
  'jar',
  'bottle',
  'box',
  'bag',
  'package',
  'packet',
  'clove',
  'head',
  'bunch',
  'stalk',
  'sprig',
  'slice',
  'stick',
  'piece',
  'fillet',
  'breast',
  'pinch',
  'dash',
  'handful',
  'dozen',
]

const NO_PLURAL = new Set(['g', 'kg', 'oz', 'lb', 'ml', 'l', 'tsp', 'tbsp', 'fl oz', 'dozen'])
const PLURAL: Record<string, string> = { box: 'boxes', bunch: 'bunches', dash: 'dashes', pinch: 'pinches' }

/** 1.5 -> "1 1/2", 0.333 -> "1/3". Nearest 1/8 or 1/3. */
export function formatQuantity(q: number): string {
  if (q >= 10) return String(Math.round(q))
  const cands = [8, 3].map((d) => ({ n: Math.round(q * d), d }))
  let { n, d } = cands.reduce((a, b) => (Math.abs(a.n / a.d - q) <= Math.abs(b.n / b.d - q) ? a : b))
  if (n === 0) [n, d] = [1, 8]
  const whole = Math.floor(n / d)
  let rem = n % d
  if (!rem) return String(whole)
  const g = gcd(rem, d)
  rem /= g
  const den = d / g
  return whole ? `${whole} ${rem}/${den}` : `${rem}/${den}`
}
const gcd = (a: number, b: number): number => (b ? gcd(b, a % b) : a)

export function formatAmount(quantity: number | null | undefined, unit: string | null | undefined) {
  if (quantity == null) return ''
  const q = formatQuantity(quantity)
  if (!unit) return q
  const u = !NO_PLURAL.has(unit) && quantity > 1 ? (PLURAL[unit] ?? unit + 's') : unit
  return `${q} ${u}`
}

/** "1 1/2" / "1.5" / "½" -> 1.5. null for blank or unreadable. */
export function parseQuantity(s: string): number | null {
  const t = s.trim().replace('½', ' 1/2').replace('¼', ' 1/4').replace('¾', ' 3/4').replace('⅓', ' 1/3')
  if (!t) return null
  let total = 0
  for (const part of t.split(/\s+/)) {
    const [a, b] = part.split('/')
    const v = b === undefined ? Number(a) : Number(a) / Number(b)
    if (!Number.isFinite(v)) return null
    total += v
  }
  return total
}

/** Recipe tags offered on the review screen. 'bail-out': 15-minute shelf-stable fallback. */
export const TAGS = ['kid favorite', 'solo', 'bail-out']
