import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, must } from '../api/client'
import { ErrorText, Field } from '../components/Field'

export default function LoginPage({ signupOpen }: { signupOpen: boolean }) {
  const qc = useQueryClient()
  const [mode, setMode] = useState<'login' | 'signup'>(signupOpen ? 'signup' : 'login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const submit = useMutation({
    mutationFn: () => {
      const body = { email, password }
      return mode === 'signup'
        ? must(api.POST('/api/auth/signup', { body }))
        : must(api.POST('/api/auth/login', { body }))
    },
    onSuccess: () => qc.resetQueries(), // drop anything cached from a previous user
  })

  return (
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-4">
      <div className="mb-8 text-center">
        <img src="/favicon.svg" alt="" className="mx-auto h-12 w-12" />
        <h1 className="mt-3 text-2xl font-semibold tracking-tight">Plenty</h1>
        <p className="text-muted">Plan the week, shop once, stay under budget.</p>
      </div>
      <form
        className="card space-y-4 p-4"
        onSubmit={(e) => {
          e.preventDefault()
          submit.mutate()
        }}
      >
        <h2 className="text-lg font-semibold">{mode === 'signup' ? 'Create your account' : 'Sign in'}</h2>
        <Field label="Email">
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Password" hint={mode === 'signup' ? 'At least 10 characters' : undefined}>
          <input
            type="password"
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            required
            minLength={mode === 'signup' ? 10 : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <ErrorText error={submit.error} />
        <button className="btn-primary w-full" disabled={submit.isPending}>
          {mode === 'signup' ? 'Create account' : 'Sign in'}
        </button>
        {signupOpen ? (
          <button
            type="button"
            className="w-full text-sm text-brand"
            onClick={() => setMode(mode === 'signup' ? 'login' : 'signup')}
          >
            {mode === 'signup' ? 'I already have an account' : 'Create an account'}
          </button>
        ) : (
          <p className="text-center text-sm text-muted">This Plenty is private. Sign-ups are closed.</p>
        )}
      </form>
    </div>
  )
}
