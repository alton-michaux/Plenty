import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { RecipeSummary } from '../api/client'
import { ErrorText } from '../components/Field'
import { saveDraft } from '../lib/draft'
import { useImport, useRecipes, type ImportInput } from '../lib/hooks'
import { downscale } from '../lib/image'
import { PageHeader } from './StubPage'

export default function RecipesPage() {
  const { data: recipes } = useRecipes()
  const [q, setQ] = useState('')
  const shown = (recipes ?? []).filter((r) => r.title.toLowerCase().includes(q.trim().toLowerCase()))

  return (
    <>
      <PageHeader title="Recipes" sub={recipes ? `${recipes.length} saved` : undefined} />
      <input
        type="search"
        placeholder="Search recipes"
        aria-label="Search recipes"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        className="mt-3 h-[42px] w-full rounded-xl"
      />

      <AddRecipe />

      {recipes && recipes.length > 0 && <h2 className="section-label mx-0.5 mb-2.5">Your recipes</h2>}
      {shown.map((r) => (
        <RecipeCard key={r.id} r={r} />
      ))}
      {recipes && recipes.length > 0 && shown.length === 0 && (
        <p className="text-center text-sm text-muted">No recipes match “{q}”.</p>
      )}
    </>
  )
}

function RecipeCard({ r }: { r: RecipeSummary }) {
  const solo = r.tags.includes('solo') || r.servings === 1
  return (
    <Link to={`/recipes/${r.id}`} className="card mb-2.5 flex items-center gap-3 p-3">
      <div
        className={`flex h-14 w-14 flex-none items-center justify-center overflow-hidden rounded-xl ${
          solo ? 'bg-[#F3EAD7] text-amber' : 'bg-brand-tint text-brand'
        }`}
      >
        {r.image_id ? (
          <img src={`/api/uploads/${r.image_id}`} alt="" className="h-full w-full object-cover" />
        ) : (
          <BowlIcon />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[15px] font-semibold">{r.title}</p>
        <p className="mt-1 flex flex-wrap gap-x-1.5 text-[12.5px] text-muted">
          {[r.minutes && `${r.minutes} min`, r.servings && `serves ${r.servings}`, `${r.ingredient_count} ingredients`]
            .filter(Boolean)
            .join(' · ')}
        </p>
        {r.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {r.tags.map((t) => (
              <span key={t} className="rounded-full bg-brand-tint px-2.5 py-1 text-[11px] font-semibold text-brand">
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
    </Link>
  )
}

function BowlIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
      <path d="M3.5 11h17a8.5 8.5 0 0 1-17 0zM8 7c0-1.5 1-2 1-3.5M12 7c0-1.5 1-2 1-3.5M16 7c0-1.5 1-2 1-3.5" />
    </svg>
  )
}

type Mode = 'link' | 'text' | 'image' | null

/** The "Add a recipe" card: paste a link or text, or pick a screenshot. */
export function AddRecipe({ initialMode = null }: { initialMode?: Mode }) {
  const navigate = useNavigate()
  const imp = useImport()
  const [mode, setMode] = useState<Mode>(initialMode)
  const [url, setUrl] = useState('')
  const [text, setText] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const run = (input: ImportInput) =>
    imp.mutate(input, {
      onSuccess: (draft) => {
        saveDraft(draft)
        navigate('/recipes/review')
      },
    })

  const pickImage = async (f: File | undefined) => {
    if (!f) return
    setMode('image')
    run({ kind: 'image', file: await downscale(f) })
  }

  return (
    <div className="mt-1.5 mb-[18px] rounded-2xl border-[1.5px] border-dashed border-[#CFC6B6] bg-[#FBFAF6] p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-brand-tint text-brand">
          <svg
            viewBox="0 0 24 24"
            className="h-5 w-5"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path d="M12 5v14M5 12h14" />
          </svg>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold">Add a recipe</p>
          <p className="mt-0.5 text-[13px] leading-snug text-muted">
            Paste a link or the caption, pick a screenshot, or share straight from TikTok, Instagram or the web.
          </p>
        </div>
      </div>

      {imp.isPending ? (
        <p className="mt-4 flex items-center gap-2 text-sm font-medium text-brand">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand border-t-transparent" />
          Reading the recipe… this can take a few seconds.
        </p>
      ) : (
        <>
          <div className="mt-3.5 grid grid-cols-3 gap-2">
            {(
              [
                ['link', 'Link'],
                ['text', 'Text'],
                ['image', 'Screenshot'],
              ] as const
            ).map(([m, label]) => (
              <button
                key={m}
                type="button"
                onClick={() => (m === 'image' ? fileRef.current?.click() : setMode(mode === m ? null : m))}
                className={`h-11 rounded-xl text-sm font-semibold ${
                  mode === m ? 'bg-brand text-white' : 'border border-line-strong bg-white text-ink'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              pickImage(e.target.files?.[0])
              e.target.value = ''
            }}
          />

          {mode === 'link' && (
            <form
              className="mt-3 flex gap-2"
              onSubmit={(e) => {
                e.preventDefault()
                run({ kind: 'link', url: url.trim() })
              }}
            >
              <input
                type="url"
                required
                autoFocus
                placeholder="https://…"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="min-w-0 flex-1"
              />
              <button className="btn h-10 rounded-[10px] bg-brand px-4 text-sm text-white">Read</button>
            </form>
          )}
          {mode === 'text' && (
            <form
              className="mt-3"
              onSubmit={(e) => {
                e.preventDefault()
                run({ kind: 'text', text })
              }}
            >
              <textarea
                required
                autoFocus
                rows={6}
                placeholder="Paste the caption or the recipe text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                className="w-full rounded-[10px] border border-line-strong bg-white p-3 text-[15px] outline-none focus:border-brand"
              />
              <button className="btn mt-2 h-10 w-full rounded-[10px] bg-brand text-sm text-white">Read recipe</button>
            </form>
          )}
        </>
      )}
      <div className="mt-2">
        <ErrorText error={imp.error} />
      </div>
    </div>
  )
}
