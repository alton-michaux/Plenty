import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { Household, PlanSlot } from '../api/client'
import { ErrorText } from '../components/Field'
import { daysUntil, money0, shortDate, toCents } from '../lib/format'
import { usePlan, usePlanEntry, useRecipes } from '../lib/hooks'

const DOW = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
const DEFAULT_OUT_CENTS = 2500

// API dates are YYYY-MM-DD; do date math on local dates so nothing shifts a day.
const parse = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}
const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const addDays = (s: string, n: number) => {
  const d = parse(s)
  d.setDate(d.getDate() + n)
  return iso(d)
}

export default function PlanPage({ household: h }: { household: Household }) {
  const [start, setStart] = useState<string | undefined>()
  const { data: week, error } = usePlan(start)
  const [editing, setEditing] = useState<PlanSlot | null>(null)
  const p = h.period
  const toPayday = daysUntil(p.next_payday)

  if (error) return <p className="py-10 text-center text-sm text-muted">{error.message}</p>
  if (!week) return null

  const kidSlots = week.slots.filter((s) => s.kids_home)
  const soloSlots = week.slots.filter((s) => !s.kids_home)
  const dayName = (s: PlanSlot) => DOW[parse(s.day).getDay()]
  const range = (slots: PlanSlot[]) =>
    slots.length ? `${cap(dayName(slots[0]))}–${cap(dayName(slots[slots.length - 1]))}` : ''
  const cooked = kidSlots.filter((s) => s.entry?.kind === 'recipe').length
  const out = kidSlots.filter((s) => s.entry?.kind === 'out').length
  const planned = week.slots.filter((s) => s.entry).length
  const outCents = week.period_out_cents

  return (
    <>
      <header className="flex items-end justify-between gap-2 pb-1.5">
        <div>
          <h1 className="text-[26px] font-bold tracking-[-0.5px]">{start ? 'Week of' : 'This week'}</h1>
          <p className="mt-0.5 text-[13px] text-muted">
            {shortDate(week.start)} – {shortDate(week.end)}
            {kidSlots.length > 0 && ` · kids here ${range(kidSlots)}`}
          </p>
        </div>
        <div className="flex gap-1">
          <WeekButton label="Previous week" d="M15 5l-7 7 7 7" onClick={() => setStart(addDays(week.start, -7))} />
          {start && (
            <button type="button" className="px-2 text-xs font-semibold text-brand" onClick={() => setStart(undefined)}>
              Today
            </button>
          )}
          <WeekButton label="Next week" d="M9 5l7 7-7 7" onClick={() => setStart(addDays(week.start, 7))} />
        </div>
      </header>

      <div className="card mt-2 mb-1.5 p-3.5">
        <div className="flex items-baseline justify-between">
          <span className="section-label">Pay-period budget</span>
          <span className="text-[13px] text-faint">
            {toPayday <= 0 ? 'Payday today' : toPayday === 1 ? 'Payday tomorrow' : `${toPayday} days to payday`}
          </span>
        </div>
        <div className="mt-2.5 h-[9px] overflow-hidden rounded-full bg-line">
          <div
            className="h-full rounded-full bg-amber"
            style={{ width: `${Math.min(100, (outCents / h.budget_cents) * 100)}%` }}
          />
        </div>
        <div className="mt-2 flex items-baseline justify-between">
          <span className="text-sm">
            <strong className="text-amber-dark">{money0(outCents)}</strong> eating out of {money0(h.budget_cents)}
          </span>
        </div>
        <p className="mt-1 text-xs text-faint">Grocery spending joins this bar once receipts are in.</p>
      </div>

      {kidSlots.length > 0 && (
        <Section label={`Kids here · ${range(kidSlots)}`} aside={`cook ${cooked}, out ${out}`}>
          {kidSlots.map((s) => (
            <SlotCard key={s.day + s.slot} s={s} dow={dayName(s)} onClick={() => setEditing(s)} />
          ))}
        </Section>
      )}
      <Section label={kidSlots.length ? `Just me · ${range(soloSlots)}` : 'Dinners'} aside="cheap & easy">
        {soloSlots.map((s) => (
          <SlotCard key={s.day + s.slot} s={s} dow={dayName(s)} onClick={() => setEditing(s)} />
        ))}
      </Section>

      <Link to="/list" className="btn-primary mt-2 w-full">
        {planned ? 'Make the grocery list' : 'See the grocery list'}
      </Link>
      <p className="mt-5 text-center text-sm">
        <Link to="/setup" className="font-semibold text-brand">
          Edit household
        </Link>
      </p>

      {editing && <SlotSheet s={editing} dow={dayName(editing)} onClose={() => setEditing(null)} />}
    </>
  )
}

const cap = (s: string) => s[0] + s.slice(1).toLowerCase()

function WeekButton({ label, d, onClick }: { label: string; d: string; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="flex h-9 w-9 items-center justify-center rounded-full border border-line-strong bg-white"
    >
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
        <path d={d} />
      </svg>
    </button>
  )
}

function Section({ label, aside, children }: { label: string; aside: string; children: React.ReactNode }) {
  return (
    <>
      <h2 className="section-label mx-0.5 mt-4 mb-2 flex items-baseline justify-between">
        <span>{label}</span>
        <span className="font-semibold tracking-normal text-faint normal-case">{aside}</span>
      </h2>
      {children}
    </>
  )
}

function SlotCard({ s, dow, onClick }: { s: PlanSlot; dow: string; onClick: () => void }) {
  const e = s.entry
  const isOut = e?.kind === 'out'
  const title =
    e?.kind === 'recipe' ? e.recipe_title : isOut ? 'Eating out' : e?.kind === 'leftovers' ? 'Leftovers' : null
  const sub = isOut
    ? 'Planned night out · tap to cook instead'
    : e
      ? `${s.slot === 'lunch' ? 'Lunch' : 'Dinner'} · serves ${e.servings}`
      : `Plan ${s.slot} · for ${s.default_servings}`
  return (
    <button
      type="button"
      onClick={onClick}
      className={`card mb-2 flex w-full items-center gap-3 p-3 text-left ${
        isOut ? 'border-amber-edge bg-amber-tint' : !e ? 'border-dashed' : ''
      }`}
    >
      <div className="w-10 flex-none text-center">
        <div className={`text-[11px] font-bold tracking-[.5px] ${isOut ? 'text-amber' : 'text-faint'}`}>{dow}</div>
        <div className={`text-base font-bold ${isOut ? 'text-amber-dark' : ''}`}>{Number(s.day.slice(-2))}</div>
      </div>
      <div className="min-w-0 flex-1">
        <p className={`truncate text-[14.5px] font-semibold ${title ? '' : 'text-faint'}`}>{title ?? '+ Add a meal'}</p>
        <p className={`mt-0.5 text-[12.5px] ${isOut ? 'text-amber-dark' : 'text-muted'}`}>{sub}</p>
      </div>
      {isOut && (
        <div className="flex-none text-right">
          <div className="text-sm font-bold text-amber-dark">{money0(e.amount_cents ?? 0)}</div>
          <div className="text-[11px] text-amber">save it all</div>
        </div>
      )}
      {e?.kind === 'leftovers' && <div className="flex-none text-sm font-bold text-brand">$0</div>}
    </button>
  )
}

/** Bottom sheet: choose what this meal is. */
function SlotSheet({ s, dow, onClose }: { s: PlanSlot; dow: string; onClose: () => void }) {
  const { data: recipes = [] } = useRecipes()
  const { put, clear, busy } = usePlanEntry()
  const [q, setQ] = useState('')
  const [servings, setServings] = useState(s.entry?.servings ?? s.default_servings)
  const [outAmount, setOutAmount] = useState(String((s.entry?.amount_cents ?? DEFAULT_OUT_CENTS) / 100))
  const ctx = { day: s.day, slot: s.slot }
  const done = { onSuccess: onClose }

  // Kid meals: kid favorites first; solo meals: solo recipes first
  const prefer = s.kids_home ? 'kid favorite' : 'solo'
  const shown = recipes
    .filter((r) => r.title.toLowerCase().includes(q.trim().toLowerCase()))
    .sort((a, b) => Number(b.tags.includes(prefer)) - Number(a.tags.includes(prefer)))

  return (
    <div className="fixed inset-0 z-20 flex flex-col justify-end bg-black/30" onClick={onClose}>
      <div
        className="mx-auto flex max-h-[85dvh] w-full max-w-xl flex-col rounded-t-3xl bg-ground pb-[env(safe-area-inset-bottom)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 pt-4 pb-2">
          <h2 className="text-lg font-bold">
            {cap(dow)} {s.slot}
            <span className="ml-2 text-sm font-medium text-muted">{s.kids_home ? 'kids here' : 'just you'}</span>
          </h2>
          <button type="button" onClick={onClose} className="text-sm font-semibold text-brand">
            Close
          </button>
        </div>

        <div className="flex items-center justify-between px-4 pb-3">
          <span className="text-sm text-muted">Cooking for</span>
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label="Fewer"
              className="h-8 w-8 rounded-full border border-line-strong font-semibold text-brand"
              onClick={() => setServings(Math.max(1, servings - 1))}
            >
              −
            </button>
            <span className="w-5 text-center font-bold">{servings}</span>
            <button
              type="button"
              aria-label="More"
              className="h-8 w-8 rounded-full border border-line-strong font-semibold text-brand"
              onClick={() => setServings(Math.min(50, servings + 1))}
            >
              +
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 px-4 pb-3">
          <form
            className="card flex items-center gap-2 border-amber-edge bg-amber-tint p-2.5"
            onSubmit={(e) => {
              e.preventDefault()
              put.mutate({ ...ctx, body: { kind: 'out', servings, amount_cents: toCents(outAmount) ?? 0 } }, done)
            }}
          >
            <span className="text-amber-dark">$</span>
            <input
              aria-label="Eating out budget"
              inputMode="decimal"
              value={outAmount}
              onChange={(e) => setOutAmount(e.target.value)}
              className="h-9 w-14 px-2 text-center"
            />
            <button disabled={busy} className="flex-1 text-sm font-semibold text-amber-dark">
              Eat out
            </button>
          </form>
          <button
            type="button"
            disabled={busy}
            className="card p-2.5 text-sm font-semibold text-brand"
            onClick={() => put.mutate({ ...ctx, body: { kind: 'leftovers', servings } }, done)}
          >
            Leftovers
          </button>
        </div>

        <div className="px-4">
          <input
            type="search"
            placeholder="Search your recipes"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-full"
          />
        </div>
        <ul className="mt-2 flex-1 overflow-y-auto px-4 pb-3">
          {shown.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                disabled={busy}
                onClick={() => put.mutate({ ...ctx, body: { kind: 'recipe', recipe_id: r.id, servings } }, done)}
                className={`card mb-2 flex w-full items-center gap-3 p-3 text-left ${
                  s.entry?.recipe_id === r.id ? 'border-brand' : ''
                }`}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14.5px] font-semibold">{r.title}</p>
                  <p className="mt-0.5 text-[12.5px] text-muted">
                    {[r.minutes && `${r.minutes} min`, r.servings && `makes ${r.servings}`, ...r.tags]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                </div>
              </button>
            </li>
          ))}
          {recipes.length === 0 && (
            <li className="py-6 text-center text-sm text-muted">
              No recipes yet.{' '}
              <Link to="/recipes" className="font-semibold text-brand">
                Add one
              </Link>
            </li>
          )}
        </ul>

        {s.entry && (
          <div className="border-t border-line px-4 py-3">
            <button
              type="button"
              disabled={busy}
              className="w-full text-sm font-semibold text-rose-700"
              onClick={() => clear.mutate(ctx, done)}
            >
              Clear this meal
            </button>
          </div>
        )}
        <div className="px-4">
          <ErrorText error={put.error ?? clear.error} />
        </div>
      </div>
    </div>
  )
}
