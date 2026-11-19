import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export const api = createClient<paths>({ baseUrl: '' })

type S = components['schemas']
export type AuthStatus = S['AuthStatus']
export type Household = S['HouseholdOut']
export type HouseholdIn = S['HouseholdIn']
export type Slot = HouseholdIn['kids_from_slot']
export type RecipeDraft = S['RecipeDraft']
export type DraftLine = S['DraftLine']
export type RecipeIn = S['RecipeIn']
export type LineIn = S['LineIn']
export type Recipe = S['RecipeOut']
export type RecipeSummary = S['RecipeSummary']
export type Ingredient = S['IngredientOut']
export type Week = S['WeekOut']
export type PlanSlot = S['SlotOut']
export type EntryIn = S['EntryIn']
export type GroceryList = S['ListOut']
export type GroceryItem = S['ItemOut']

export class ApiError extends Error {
  readonly status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

/** Unwrap an openapi-fetch result, throwing on API errors so React Query sees them. */
export async function must<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await p
  if (error !== undefined || !response.ok) {
    const detail = (error as { detail?: unknown })?.detail
    throw new ApiError(typeof detail === 'string' ? detail : `Request failed (${response.status})`, response.status)
  }
  return data as T
}
