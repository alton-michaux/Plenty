import type { GroceryItem } from '../api/client'

/** Group items by aisle, in store order. */
export function byAisle(items: GroceryItem[], aisles: string[]) {
  const groups = new Map<string, GroceryItem[]>()
  for (const a of aisles) groups.set(a, [])
  for (const i of items) {
    if (!groups.has(i.aisle)) groups.set(i.aisle, [])
    groups.get(i.aisle)!.push(i)
  }
  return [...groups].filter(([, xs]) => xs.length > 0)
}
