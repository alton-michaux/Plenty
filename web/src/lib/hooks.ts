import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api, must, type HouseholdIn, type RecipeIn } from '../api/client'

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
