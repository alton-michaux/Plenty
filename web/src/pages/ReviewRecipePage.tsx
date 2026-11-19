import { useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import type { DraftLine, Recipe, RecipeDraft, RecipeIn } from '../api/client'
import { ErrorText } from '../components/Field'
import { clearDraft, loadDraft } from '../lib/draft'
import { useAisles, useIngredients, useRecipe, useSaveRecipe } from '../lib/hooks'
import { TAGS, UNITS, formatAmount, formatQuantity, parseQuantity } from '../lib/units'

type Line = DraftLine & { key: number }
type Form = Omit<RecipeIn, 'lines'> & { lines: Line[] }

let nextKey = 1
const withKeys = (lines: DraftLine[]): Line[] => lines.map((l) => ({ ...l, key: nextKey++ }))

function fromDraft(d: RecipeDraft): Form {
  return { ...d, tags: d.servings === 1 ? ['solo'] : [], lines: withKeys(d.lines) }
}

function fromRecipe(r: Recipe): Form {
  return {
    title: r.title,
    servings: r.servings,
    minutes: r.minutes,
    steps: r.steps,
    tags: r.tags,
    source_url: r.source_url,
    source_kind: r.source_kind as RecipeIn['source_kind'],
    image_id: r.image_id,
    lines: withKeys(
      r.lines.map((l) => ({
        original: l.original,
        quantity: l.quantity,
        unit: l.unit,
        name: l.name,
        aisle: l.aisle,
        note: l.note,
        ingredient_id: l.ingredient_id,
        problem: null,
        matched: true,
      })),
    ),
  }
}

/** /recipes/review: confirm an import. */
export function ReviewDraftPage() {
  const draft = loadDraft()
  if (!draft) return <Navigate to="/recipes" replace />
  return <ReviewForm initial={fromDraft(draft)} draft={draft} />
}

/** /recipes/:id/edit */
export function EditRecipePage() {
  const id = Number(useParams().id)
  const { data } = useRecipe(id)
  if (!data) return null
  return <ReviewForm initial={fromRecipe(data)} recipeId={id} />
}

const SOURCE: Record<string, string> = {
  link: 'Imported from a link',
  text: 'Imported from text',
  image: 'Imported from a screenshot',
  manual: 'Added by hand',
}
const READ_BY: Record<string, string> = {
  model: 'We read it. Check it over.',
  page: "From the site's recipe data. Check it over.",
  parser: 'Read line by line. Check each ingredient.',
}

function ReviewForm({ initial, draft, recipeId }: { initial: Form; draft?: RecipeDraft; recipeId?: number }) {
  const navigate = useNavigate()
  const save = useSaveRecipe()
  const { data: aisles = [] } = useAisles()
  const { data: ingredients = [] } = useIngredients()
  const [form, setForm] = useState<Form>(initial)
  const [open, setOpen] = useState<number | null>(null)
  const set = (patch: Partial<Form>) => setForm((f) => ({ ...f, ...patch }))
  const setLine = (key: number, patch: Partial<Line>) =>
    setForm((f) => ({ ...f, lines: f.lines.map((l) => (l.key === key ? { ...l, ...patch } : l)) }))
  const problems = form.lines.filter((l) => l.problem).length

  const submit = () => {
    const body: RecipeIn = {
      ...form,
      lines: form.lines.map(({ original, quantity, unit, name, aisle, note, ingredient_id }) => ({
        original: original || name,
        quantity,
        unit,
        name,
        aisle,
        note,
        ingredient_id,
      })),
    }
    save.mutate(
      { id: recipeId, body },
      {
        onSuccess: (r) => {
          clearDraft()
          navigate(`/recipes/${r.id}`, { replace: true })
        },
      },
    )
  }
  const discard = () => {
    clearDraft()
    navigate(recipeId ? `/recipes/${recipeId}` : '/recipes', { replace: true })
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-xl flex-col">
      <header className="flex items-center gap-1 border-b border-[#EAE4DA] bg-white px-3 pt-[max(0.875rem,env(safe-area-inset-top))] pb-2.5">
        <button
          type="button"
          onClick={discard}
          aria-label="Back"
          className="-ml-1 flex h-10 w-10 items-center justify-center"
        >
          <svg
            viewBox="0 0 24 24"
            className="h-5 w-5"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path d="M15 5l-7 7 7 7" />
          </svg>
        </button>
        <h1 className="text-base font-bold">{recipeId ? 'Edit recipe' : 'Review recipe'}</h1>
      </header>

      <div className="flex-1 px-4 pb-6">
        {draft && (
          <div className="mt-3 mb-3.5 flex items-center gap-2.5">
            {draft.image_id && (
              <img
                src={`/api/uploads/${draft.image_id}`}
                alt=""
                className="h-11 w-11 flex-none rounded-xl object-cover"
              />
            )}
            <div className="min-w-0 flex-1">
              <span className="rounded-full bg-[#F0EDE6] px-2.5 py-1 text-[11px] font-semibold text-muted">
                {SOURCE[draft.source_kind]}
              </span>
              <p className="mt-1.5 text-[12.5px] text-faint">{draft.warning ?? READ_BY[draft.read_by]}</p>
            </div>
          </div>
        )}

        <label className="section-label mt-3 block" htmlFor="title">
          Recipe name
        </label>
        <input
          id="title"
          value={form.title}
          onChange={(e) => set({ title: e.target.value })}
          className="mt-1.5 mb-3.5 h-[46px] w-full rounded-xl font-semibold"
        />

        <div className="card mb-4 flex items-center justify-between px-3.5 py-3">
          <div>
            <div className="text-[11.5px] text-faint">Servings</div>
            <div className="mt-1 flex items-center gap-2.5">
              <Step label="Fewer servings" onClick={() => set({ servings: Math.max(1, (form.servings ?? 2) - 1) })}>
                −
              </Step>
              <span className="min-w-4 text-center text-[17px] font-bold">{form.servings ?? '?'}</span>
              <Step label="More servings" onClick={() => set({ servings: Math.min(100, (form.servings ?? 0) + 1) })}>
                +
              </Step>
            </div>
          </div>
          <label className="text-right">
            <div className="text-[11.5px] text-faint">Time (min)</div>
            <input
              inputMode="numeric"
              value={form.minutes ?? ''}
              onChange={(e) => set({ minutes: Number(e.target.value.replace(/\D/g, '')) || null })}
              className="mt-1 h-9 w-20 text-center font-bold"
            />
          </label>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          {TAGS.map((t) => {
            const on = form.tags?.includes(t)
            return (
              <button
                key={t}
                type="button"
                className={on ? 'chip-on' : 'chip'}
                onClick={() => set({ tags: on ? form.tags!.filter((x) => x !== t) : [...(form.tags ?? []), t] })}
              >
                {t}
              </button>
            )
          })}
        </div>

        <h2 className="section-label mx-0.5 mb-2">
          Ingredients · {form.lines.length}
          {problems > 0 && <span className="text-amber-dark normal-case"> · {problems} to check</span>}
        </h2>
        <ul className="card mb-2 divide-y divide-[#EFEAE0] overflow-hidden">
          {form.lines.map((l) =>
            open === l.key ? (
              <LineEditor
                key={l.key}
                line={l}
                aisles={aisles}
                onChange={(patch) => setLine(l.key, patch)}
                onDone={() => setOpen(null)}
                onRemove={() => {
                  set({ lines: form.lines.filter((x) => x.key !== l.key) })
                  setOpen(null)
                }}
              />
            ) : (
              <li key={l.key}>
                <button
                  type="button"
                  onClick={() => setOpen(l.key)}
                  className={`flex w-full items-center gap-3 px-3.5 py-3 text-left ${l.problem ? 'bg-amber-tint' : ''}`}
                >
                  <span className={`w-[70px] flex-none text-sm font-semibold ${l.problem ? 'text-amber-dark' : ''}`}>
                    {formatAmount(l.quantity, l.unit) || (l.problem ? '?' : '–')}
                  </span>
                  <span className="min-w-0 flex-1 text-sm">
                    {l.name}
                    {l.note && <span className="text-faint">, {l.note}</span>}
                    {l.problem && <span className="text-xs text-amber-dark"> · {l.problem}</span>}
                    {!l.problem && !l.matched && <span className="text-xs text-faint"> · new</span>}
                  </span>
                  <span className="text-xs font-semibold text-brand">{l.problem ? 'Set' : 'Edit'}</span>
                </button>
              </li>
            ),
          )}
        </ul>
        <button
          type="button"
          className="mb-4 text-sm font-semibold text-brand"
          onClick={() => {
            const key = nextKey++
            set({
              lines: [
                ...form.lines,
                { key, original: '', quantity: null, unit: null, name: '', aisle: 'Other', note: null, matched: false },
              ],
            })
            setOpen(key)
          }}
        >
          + Add ingredient
        </button>
        <datalist id="ingredient-names">
          {ingredients.map((i) => (
            <option key={i.id} value={i.name} />
          ))}
        </datalist>

        <label className="section-label mx-0.5 mb-2 block" htmlFor="steps">
          Steps · one per line
        </label>
        <textarea
          id="steps"
          rows={Math.min(12, Math.max(4, form.steps!.length + 1))}
          value={form.steps!.join('\n')}
          onChange={(e) => set({ steps: e.target.value.split('\n') })}
          className="w-full rounded-xl border border-line-strong bg-white p-3 text-sm outline-none focus:border-brand"
        />
        <ErrorText error={save.error} />
      </div>

      <div className="sticky bottom-0 flex gap-2.5 border-t border-[#EAE4DA] bg-white px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <button type="button" onClick={discard} className="btn h-[52px] border border-line-strong px-[18px] text-muted">
          Discard
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={save.isPending || !form.title.trim() || form.lines.some((l) => !l.name.trim())}
          className="btn-primary h-[52px] flex-1"
        >
          {recipeId ? 'Save' : 'Save to recipes'}
        </button>
      </div>
    </div>
  )
}

function Step({ label, onClick, children }: { label: string; onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="h-8 w-8 rounded-full border border-line-strong text-lg leading-none font-semibold text-brand"
    >
      {children}
    </button>
  )
}

function LineEditor({
  line,
  aisles,
  onChange,
  onDone,
  onRemove,
}: {
  line: Line
  aisles: string[]
  onChange: (p: Partial<Line>) => void
  onDone: () => void
  onRemove: () => void
}) {
  const [qty, setQty] = useState(line.quantity == null ? '' : formatQuantity(line.quantity))
  return (
    <li className="space-y-2 bg-[#FBFAF6] px-3.5 py-3">
      {line.original && <p className="text-xs text-faint">From: “{line.original}”</p>}
      <div className="grid grid-cols-[5rem_1fr] gap-2">
        <input
          aria-label="Amount"
          placeholder="Amount"
          inputMode="decimal"
          value={qty}
          onChange={(e) => {
            setQty(e.target.value)
            onChange({ quantity: parseQuantity(e.target.value), problem: null })
          }}
        />
        <select
          aria-label="Unit"
          value={line.unit ?? ''}
          onChange={(e) => onChange({ unit: e.target.value || null, problem: null })}
        >
          <option value="">(whole items)</option>
          {UNITS.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </div>
      <input
        aria-label="Item"
        placeholder="Item, e.g. chicken thigh"
        list="ingredient-names"
        autoFocus={!line.name}
        value={line.name}
        onChange={(e) => onChange({ name: e.target.value, matched: false })}
        className="w-full"
      />
      <div className="grid grid-cols-2 gap-2">
        <input
          aria-label="Note"
          placeholder="Note (diced…)"
          value={line.note ?? ''}
          onChange={(e) => onChange({ note: e.target.value || null })}
        />
        <select aria-label="Aisle" value={line.aisle} onChange={(e) => onChange({ aisle: e.target.value })}>
          {aisles.map((a) => (
            <option key={a}>{a}</option>
          ))}
        </select>
      </div>
      <div className="flex justify-between pt-1">
        <button type="button" onClick={onRemove} className="text-sm font-semibold text-rose-700">
          Remove
        </button>
        <button
          type="button"
          onClick={onDone}
          disabled={!line.name.trim()}
          className="text-sm font-semibold text-brand"
        >
          Done
        </button>
      </div>
    </li>
  )
}
