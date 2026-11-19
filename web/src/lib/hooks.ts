import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api, must, type EntryIn, type GroceryList, type HouseholdIn, type RecipeIn } from '../api/client'

export const useAuth = () =>
  useQuery({ queryKey: ['auth'], queryFn: () => must(api.GET('/api/auth/status')), staleTime: Infinity })

/** null until the household is set up (the API 404s). */
export const useHousehold = () =>
  useQuery({
    queryKey: ['household'],
    queryFn: async () => {
      try {
        return await must(api.GET('/api/household'))
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null
        throw e
      }
    },
  })

export function useSaveHousehold() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: HouseholdIn) => must(api.PUT('/api/household', { body })),
    onSuccess: (data) => qc.setQueryData(['household'], data),
  })
}

export const useRecipes = () => useQuery({ queryKey: ['recipes'], queryFn: () => must(api.GET('/api/recipes')) })

export const useRecipe = (id: number) =>
  useQuery({
    queryKey: ['recipe', id],
    queryFn: () => must(api.GET('/api/recipes/{recipe_id}', { params: { path: { recipe_id: id } } })),
  })

export const useIngredients = () =>
  useQuery({ queryKey: ['ingredients'], queryFn: () => must(api.GET('/api/ingredients')) })

export const useAisles = () =>
  useQuery({ queryKey: ['aisles'], queryFn: () => must(api.GET('/api/aisles')), staleTime: Infinity })

/** Saving or deleting a recipe can change ingredients, the plan and the list. */
function useRecipeInvalidate() {
  const qc = useQueryClient()
  return () => {
    for (const key of ['recipes', 'recipe', 'ingredients', 'plan', 'list']) qc.invalidateQueries({ queryKey: [key] })
  }
}

export function useSaveRecipe() {
  const invalidate = useRecipeInvalidate()
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: RecipeIn }) =>
      id
        ? must(api.PUT('/api/recipes/{recipe_id}', { params: { path: { recipe_id: id } }, body }))
        : must(api.POST('/api/recipes', { body })),
    onSuccess: invalidate,
  })
}

export function useDeleteRecipe() {
  const invalidate = useRecipeInvalidate()
  return useMutation({
    mutationFn: (id: number) => must(api.DELETE('/api/recipes/{recipe_id}', { params: { path: { recipe_id: id } } })),
    onSuccess: invalidate,
  })
}

export type ImportInput =
  { kind: 'link'; url: string } | { kind: 'text'; text: string; url?: string } | { kind: 'image'; file: Blob }

export function useImport() {
  return useMutation({
    mutationFn: (input: ImportInput) => {
      if (input.kind === 'link') return must(api.POST('/api/import/link', { body: { url: input.url } }))
      if (input.kind === 'text')
        return must(api.POST('/api/import/text', { body: { text: input.text, url: input.url ?? null } }))
      return must(
        api.POST('/api/import/image', {
          body: { file: input.file as unknown as string },
          bodySerializer: () => {
            const fd = new FormData()
            fd.append('file', input.file, 'recipe.jpg')
            return fd
          },
        }),
      )
    },
  })
}

// --- Plan ---------------------------------------------------------------------------------

export const usePlan = (start?: string) =>
  useQuery({
    queryKey: ['plan', start ?? 'current'],
    queryFn: () => must(api.GET('/api/plan', { params: { query: { start: start ?? null } } })),
  })

export function usePlanEntry() {
  const qc = useQueryClient()
  const done = () => {
    qc.invalidateQueries({ queryKey: ['plan'] })
    qc.invalidateQueries({ queryKey: ['list'] })
  }
  const put = useMutation({
    mutationFn: ({ day, slot, body }: { day: string; slot: string; body: EntryIn }) =>
      must(api.PUT('/api/plan/{day}/{slot}', { params: { path: { day, slot: slot as 'dinner' } }, body })),
    onSuccess: done,
  })
  const clear = useMutation({
    mutationFn: ({ day, slot }: { day: string; slot: string }) =>
      must(api.DELETE('/api/plan/{day}/{slot}', { params: { path: { day, slot: slot as 'dinner' } } })),
    onSuccess: done,
  })
  return { put, clear, busy: put.isPending || clear.isPending }
}

// --- Grocery list -------------------------------------------------------------------------
// The list is cached on the phone so shop mode still opens with a weak signal in the store.
// Check-offs update instantly; while offline, TanStack pauses them and sends them when back online.

const LIST_CACHE = 'plenty.list'

function cachedList(key: string): GroceryList | undefined {
  try {
    const s = localStorage.getItem(`${LIST_CACHE}.${key}`)
    return s ? (JSON.parse(s) as GroceryList) : undefined
  } catch {
    return undefined
  }
}

function cacheList(key: string, list: GroceryList) {
  try {
    localStorage.setItem(`${LIST_CACHE}.${key}`, JSON.stringify(list))
  } catch {
    /* storage full or blocked: the network copy still works */
  }
}

export const listKey = (start?: string) => ['list', start ?? 'current'] as const

export const useList = (start?: string) =>
  useQuery({
    queryKey: listKey(start),
    queryFn: async () => {
      const list = await must(api.GET('/api/list', { params: { query: { start: start ?? null } } }))
      cacheList(start ?? 'current', list)
      return list
    },
    placeholderData: () => cachedList(start ?? 'current'),
  })

export function useListActions(start?: string) {
  const qc = useQueryClient()
  const key = listKey(start)
  const setList = (list: GroceryList) => {
    qc.setQueryData(key, list)
    cacheList(start ?? 'current', list)
  }
  const query = { params: { query: { start: start ?? null } } }

  const rebuild = useMutation({
    mutationFn: () => must(api.POST('/api/list/rebuild', query)),
    onSuccess: setList,
  })
  const patch = useMutation({
    mutationFn: ({ id, ...body }: { id: number; checked?: boolean; in_pantry?: boolean }) =>
      must(api.PATCH('/api/list/items/{item_id}', { params: { path: { item_id: id } }, body })),
    onMutate: async ({ id, ...body }) => {
      await qc.cancelQueries({ queryKey: key })
      const prev = qc.getQueryData<GroceryList>(key)
      if (prev) setList({ ...prev, items: prev.items.map((i) => (i.id === id ? { ...i, ...body } : i)) })
      return { prev }
    },
    onError: (_e, _v, ctx) => ctx?.prev && setList(ctx.prev),
  })
  const add = useMutation({
    mutationFn: (name: string) => must(api.POST('/api/list/items', { ...query, body: { name } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  })
  const remove = useMutation({
    mutationFn: (id: number) => must(api.DELETE('/api/list/items/{item_id}', { params: { path: { item_id: id } } })),
    onMutate: (id) => {
      const prev = qc.getQueryData<GroceryList>(key)
      if (prev) setList({ ...prev, items: prev.items.filter((i) => i.id !== id) })
    },
  })
  return { rebuild, patch, add, remove }
}

// --- Pantry staples -----------------------------------------------------------------------

export const useStaples = () => useQuery({ queryKey: ['staples'], queryFn: () => must(api.GET('/api/pantry/staples')) })

export function useSaveStaples() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (names: string[]) => must(api.PUT('/api/pantry/staples', { body: { names } })),
    onSuccess: (data) => {
      qc.setQueryData(['staples'], data)
      qc.invalidateQueries({ queryKey: ['list'] })
    },
  })
}
