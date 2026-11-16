import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Household, HouseholdIn, Slot } from '../api/client'
import { ErrorText } from '../components/Field'
import { toCents } from '../lib/format'
import { useSaveHousehold } from '../lib/hooks'
import { DAYS, SLOTS, kidDays } from '../lib/week'

const DEFAULTS: HouseholdIn = {
  budget_cents: 20_000,
  anchor_payday: '',
  period_days: 14,
  stores: ['Food Lion', 'Walmart'],
  kids: 3,
  kids_from_day: 2,
  kids_from_slot: 'dinner',
  kids_to_day: 5,
  kids_to_slot: 'lunch',
}

// Sun-first, like the mockup's day row
const WEEK = [6, 0, 1, 2, 3, 4, 5]

/** First-launch setup (no household yet) and later edits. */
export default function SetupPage({ household }: { household?: Household }) {
  const navigate = useNavigate()
  const save = useSaveHousehold()
  const [form, setForm] = useState<HouseholdIn>(
    household ? { ...household, anchor_payday: household.period.next_payday } : DEFAULTS,
  )
  const [budget, setBudget] = useState(String(form.budget_cents / 100))
  const [newStore, setNewStore] = useState('')
  const [allStores, setAllStores] = useState(() => [...new Set([...DEFAULTS.stores!, ...(form.stores ?? [])])])
  const set = (patch: Partial<HouseholdIn>) => setForm((f) => ({ ...f, ...patch }))
  const stores = form.stores ?? []
  const home = kidDays(form as Household)

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const cents = toCents(budget)
    if (!cents) return
    save.mutate({ ...form, budget_cents: cents }, { onSuccess: () => household && navigate('/plan') })
  }

  return (
    <form onSubmit={submit} className="mx-auto flex min-h-dvh max-w-xl flex-col">
      <header className="px-4 pt-[max(1.25rem,env(safe-area-inset-top))] pb-0.5">
        <h1 className="text-2xl font-bold tracking-[-0.5px]">{household ? 'Your household' : 'Set up your kitchen'}</h1>
        <p className="mt-1 text-[13px] text-muted">Takes a minute. You can change any of it later.</p>
      </header>

      <div className="flex-1 px-4 pb-4">
        <h2 className="section-label mx-0.5 mt-[18px] mb-2.5">Who's eating</h2>
        <div className="card flex items-center gap-3 px-3.5 py-3">
          <span className="flex-1 text-sm font-semibold">You, plus kids</span>
          <Stepper value={form.kids ?? 0} onChange={(kids) => set({ kids })} />
        </div>

        {(form.kids ?? 0) > 0 && (
          <div className="card mt-3 px-3.5 py-3">
            <p className="mb-2 text-[13px] text-muted">Days the kids are here</p>
            <div className="flex justify-between gap-1.5">
              {WEEK.map((d) => (
                <span
                  key={d}
                  className={`flex h-[38px] w-10 items-center justify-center rounded-[10px] border text-xs font-bold ${
                    home.includes(d)
                      ? 'border-brand-edge bg-brand-tint text-brand-dark'
                      : 'border-[#E7E1D7] bg-white text-[#A49C8F]'
                  }`}
                >
                  {DAYS[d]}
                </span>
              ))}
            </div>
            <div className="mt-3 grid grid-cols-[auto_1fr_1fr] items-center gap-2 text-sm">
              <span className="text-muted">From</span>
              <DaySelect value={form.kids_from_day!} onChange={(kids_from_day) => set({ kids_from_day })} />
              <SlotSelect value={form.kids_from_slot!} onChange={(kids_from_slot) => set({ kids_from_slot })} />
              <span className="text-muted">Until</span>
              <DaySelect value={form.kids_to_day!} onChange={(kids_to_day) => set({ kids_to_day })} />
              <SlotSelect value={form.kids_to_slot!} onChange={(kids_to_slot) => set({ kids_to_slot })} />
            </div>
          </div>
        )}

        <h2 className="section-label mx-0.5 mt-[18px] mb-2.5">Food budget</h2>
        <div className="card divide-y divide-[#EFEAE0]">
          <label className="flex items-center gap-2.5 px-3.5 py-3">
            <span className="flex-1 text-sm font-semibold">Groceries + eating out</span>
            <span className="text-muted">$</span>
            <input
              inputMode="decimal"
              required
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              className="w-20 text-center font-semibold"
            />
          </label>
          <label className="flex items-center gap-2.5 px-3.5 py-3">
            <span className="flex-1 text-sm font-semibold">Resets</span>
            <select
              value={form.period_days}
              onChange={(e) => set({ period_days: Number(e.target.value) })}
              className="text-[13.5px] text-muted"
            >
              <option value={7}>every week</option>
              <option value={14}>every 2 weeks</option>
            </select>
          </label>
          <label className="flex items-center gap-2.5 px-3.5 py-3">
            <span className="flex-1 text-sm font-semibold">Next payday</span>
            <input
              type="date"
              required
              value={form.anchor_payday}
              onChange={(e) => set({ anchor_payday: e.target.value })}
            />
          </label>
        </div>

        <h2 className="section-label mx-0.5 mt-[18px] mb-2.5">Where you shop</h2>
        <div className="card divide-y divide-[#EFEAE0]">
          {allStores.map((s) => (
            <label key={s} className="flex cursor-pointer items-center gap-2.5 px-3.5 py-3">
              <input
                type="checkbox"
                className="h-5 w-5 accent-brand"
                checked={stores.includes(s)}
                onChange={(e) => set({ stores: e.target.checked ? [...stores, s] : stores.filter((x) => x !== s) })}
              />
              <span className="flex-1 text-sm font-semibold">{s}</span>
            </label>
          ))}
          <div className="flex items-center gap-2 px-3.5 py-2.5">
            <input
              placeholder="Add a store"
              value={newStore}
              onChange={(e) => setNewStore(e.target.value)}
              className="flex-1"
            />
            <button
              type="button"
              className="text-sm font-semibold text-brand disabled:opacity-40"
              disabled={!newStore.trim() || allStores.includes(newStore.trim())}
              onClick={() => {
                const s = newStore.trim()
                setAllStores([...allStores, s])
                set({ stores: [...stores, s] })
                setNewStore('')
              }}
            >
              + Add
            </button>
          </div>
        </div>
        <ErrorText error={save.error} />
      </div>

      <div className="sticky bottom-0 border-t border-[#EAE4DA] bg-white px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <button className="btn-primary w-full" disabled={save.isPending}>
          {household ? 'Save' : 'Start planning'}
        </button>
      </div>
    </form>
  )
}

function Stepper({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const btn = 'h-9 w-9 rounded-full border border-line-strong text-lg font-semibold text-brand disabled:opacity-30'
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        className={btn}
        disabled={value <= 0}
        onClick={() => onChange(value - 1)}
        aria-label="Fewer kids"
      >
        −
      </button>
      <span className="w-4 text-center font-semibold tabular-nums">{value}</span>
      <button
        type="button"
        className={btn}
        disabled={value >= 12}
        onClick={() => onChange(value + 1)}
        aria-label="More kids"
      >
        +
      </button>
    </div>
  )
}

function DaySelect({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <select value={value} onChange={(e) => onChange(Number(e.target.value))}>
      {WEEK.map((d) => (
        <option key={d} value={d}>
          {DAYS[d]}
        </option>
      ))}
    </select>
  )
}

function SlotSelect({ value, onChange }: { value: Slot; onChange: (v: Slot) => void }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value as Slot)}>
      {SLOTS.map((s) => (
        <option key={s} value={s}>
          {s}
        </option>
      ))}
    </select>
  )
}
