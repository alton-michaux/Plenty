import type { Household, Slot } from '../api/client'

// Weekdays follow Python's date.weekday(): Mon=0 .. Sun=6.
export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
export const SLOTS: Slot[] = ['breakfast', 'lunch', 'dinner']

/** "Wed dinner – Sat lunch" */
export function kidWindowLabel(h: Household) {
  return `${DAYS[h.kids_from_day]} ${h.kids_from_slot} – ${DAYS[h.kids_to_day]} ${h.kids_to_slot}`
}

/** Weekdays the kids are home for at least one meal, in order from the window's start. */
export function kidDays(h: Pick<Household, 'kids_from_day' | 'kids_to_day'>): number[] {
  const n = ((h.kids_to_day - h.kids_from_day + 7) % 7) + 1
  return Array.from({ length: n }, (_, i) => (h.kids_from_day + i) % 7)
}
