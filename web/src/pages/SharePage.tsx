import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ErrorText } from '../components/Field'
import { saveDraft } from '../lib/draft'
import { useImport, type ImportInput } from '../lib/hooks'
import { downscale } from '../lib/image'
import { AddRecipe } from './RecipesPage'
import { PageHeader } from './StubPage'

type Shared = {
  title: string
  text: string
  url: string
  files: { key: string; name: string; type: string; size: number }[]
}

const INBOX = 'share-inbox'
const URL_RE = /https?:\/\/\S+/

/** Read what the service worker parked from the Android share sheet (see public/sw.js). */
async function readInbox(): Promise<{ shared: Shared; image: Blob | null } | null> {
  if (!('caches' in window)) return null
  const cache = await caches.open(INBOX)
  const meta = await cache.match('/share-inbox/meta')
  if (!meta) return null
  const shared: Shared = await meta.json()
  const first = shared.files[0] && (await cache.match(shared.files[0].key))
  return { shared, image: first ? await first.blob() : null }
}

const clearInbox = () => caches.delete(INBOX)

/** Pick what to send: a screenshot beats text; a caption with a recipe beats a bare link. */
async function toImport({ shared, image }: { shared: Shared; image: Blob | null }): Promise<ImportInput | null> {
  if (image) return { kind: 'image', file: await downscale(new File([image], 'shared', { type: image.type })) }
  const all = [shared.title, shared.text].filter(Boolean).join('\n').trim()
  const url = shared.url || all.match(URL_RE)?.[0] || ''
  const words = all.replace(URL_RE, '').trim()
  if (words.length >= 60) return { kind: 'text', text: all, url: url || undefined }
  if (url) return { kind: 'link', url }
  return null
}

export default function SharePage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const imp = useImport()
  const started = useRef(false)
  const [state, setState] = useState<'reading' | 'empty' | 'failed'>('reading')

  useEffect(() => {
    if (started.current) return // StrictMode runs effects twice in dev
    started.current = true
    ;(async () => {
      const inbox = await readInbox()
      const input = inbox && (await toImport(inbox))
      if (!input) return setState('empty')
      imp.mutate(input, {
        onSuccess: async (draft) => {
          await clearInbox()
          saveDraft(draft)
          navigate('/recipes/review', { replace: true })
        },
        onError: () => setState('failed'),
      })
    })()
  }, [imp, navigate])

  const problem = params.has('error')
    ? "The share couldn't be read. Try sharing again."
    : params.has('missed')
      ? 'The share arrived before the app finished installing. Share it again.'
      : null

  return (
    <>
      <PageHeader title="Shared to Plenty" />
      {problem && (
        <div className="card mt-3 border-amber-edge bg-amber-tint p-4 text-sm text-amber-dark">{problem}</div>
      )}
      {state === 'reading' && !problem && (
        <p className="mt-6 flex items-center gap-2 text-sm font-medium text-brand">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand border-t-transparent" />
          Reading the recipe… this can take a few seconds.
        </p>
      )}
      {state === 'failed' && (
        <div className="mt-3">
          <ErrorText error={imp.error} />
          <p className="mt-2 text-sm text-muted">Paste the caption or pick a screenshot instead:</p>
        </div>
      )}
      {state === 'empty' && !problem && (
        <p className="mt-3 text-sm text-muted">
          Nothing shared yet. From TikTok, Instagram or a recipe site, tap Share and pick Plenty.
        </p>
      )}
      {(state !== 'reading' || problem) && <AddRecipe initialMode="text" />}
    </>
  )
}
