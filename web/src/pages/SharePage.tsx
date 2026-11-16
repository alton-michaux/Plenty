import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PageHeader } from './StubPage'

type Shared = {
  title: string
  text: string
  url: string
  files: { key: string; name: string; type: string; size: number }[]
  received_at: string
}

/** What the service worker parked from the Android share sheet (see public/sw.js).
 * Phase 0 just shows it; phase 1 sends it to recipe extraction and the confirm screen. */
export default function SharePage() {
  const [params] = useSearchParams()
  const [shared, setShared] = useState<Shared | null | undefined>(undefined)
  const [images, setImages] = useState<string[]>([])

  useEffect(() => {
    const urls: string[] = []
    ;(async () => {
      if (!('caches' in window)) return setShared(null)
      const cache = await caches.open('share-inbox')
      const meta = await cache.match('/share-inbox/meta')
      if (!meta) return setShared(null)
      const data: Shared = await meta.json()
      for (const f of data.files) {
        const r = await cache.match(f.key)
        if (r) urls.push(URL.createObjectURL(await r.blob()))
      }
      setImages(urls)
      setShared(data)
    })()
    return () => urls.forEach((u) => URL.revokeObjectURL(u))
  }, [])

  const problem = params.has('error')
    ? "The share couldn't be read. Try sharing again."
    : params.has('missed')
      ? 'The share arrived before the app finished installing. Share it again.'
      : null

  return (
    <>
      <PageHeader title="Shared to Plenty" sub="Recipe import arrives in phase 1. For now this shows what came in." />
      {problem && (
        <div className="card mt-3 border-amber-edge bg-amber-tint p-4 text-sm text-amber-dark">{problem}</div>
      )}
      {shared === null && !problem && (
        <div className="card mt-3 p-4 text-sm text-muted">
          Nothing shared yet. From TikTok, Instagram or a recipe site, tap Share and pick Plenty.
        </div>
      )}
      {shared && (
        <div className="card mt-3 space-y-3 p-4 text-sm">
          <Row label="Title" value={shared.title} />
          <Row label="Text" value={shared.text} />
          <Row label="Link" value={shared.url} />
          {images.map((src, i) => (
            <img
              key={src}
              src={src}
              alt={shared.files[i]?.name ?? ''}
              className="max-h-80 rounded-xl border border-line"
            />
          ))}
          <p className="text-xs text-faint">Received {new Date(shared.received_at).toLocaleString()}</p>
        </div>
      )}
    </>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  if (!value) return null
  return (
    <div>
      <p className="section-label">{label}</p>
      <p className="mt-0.5 break-words whitespace-pre-wrap">{value}</p>
    </div>
  )
}
