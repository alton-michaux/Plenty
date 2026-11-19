import type { RecipeDraft } from '../api/client'

// The draft being reviewed survives a reload (and the app being backgrounded mid-review).
const KEY = 'plenty.draft'

export function saveDraft(d: RecipeDraft) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(d))
  } catch {
    /* private mode / full storage: the in-memory copy still works */
  }
}

export function loadDraft(): RecipeDraft | null {
  try {
    const s = sessionStorage.getItem(KEY)
    return s ? (JSON.parse(s) as RecipeDraft) : null
  } catch {
    return null
  }
}

export function clearDraft() {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    /* ignore */
  }
}
