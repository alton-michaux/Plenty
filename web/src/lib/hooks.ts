import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api, must, type HouseholdIn } from '../api/client'

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
