import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorText } from '../components/Field'
import { shortDate } from '../lib/format'
import { useAisles, useList, useListActions } from '../lib/hooks'
import { byAisle } from '../lib/list'

export default function ListPage() {
  const { data: list, error } = useList()
  const { data: aisles = [] } = useAisles()
  const { rebuild, patch, add, remove } = useListActions()
  const [newItem, setNewItem] = useState('')

  if (error && !list) return <p className="py-10 text-center text-sm text-muted">{error.message}</p>
  if (!list) return null

  const toBuy = list.items.filter((i) => !i.in_pantry)
  const inPantry = list.items.length - toBuy.length

  return (
    <>
      <header className="pb-1.5">
        <h1 className="text-[26px] font-bold tracking-[-0.5px]">Grocery list</h1>
        <p className="mt-0.5 text-[13px] text-muted">
          {shortDate(list.week_start)} – {shortDate(list.week_end)} · one trip
        </p>
      </header>

      {list.stale && (
        <div className="card mt-2 flex items-center gap-3 border-amber-edge bg-amber-tint p-3.5">
          <p className="flex-1 text-sm text-amber-dark">The plan changed since this list was made.</p>
          <button
            type="button"
            disabled={rebuild.isPending}
            onClick={() => rebuild.mutate()}
            className="btn h-9 rounded-[10px] bg-amber px-3 text-sm text-white"
          >
            Update list
          </button>
        </div>
      )}

      <div className="card mt-2 mb-1.5 flex items-baseline justify-between p-3.5">
        <span className="text-sm">
          <strong>{toBuy.length}</strong> to buy
          {inPantry > 0 && <span className="text-muted"> · {inPantry} in pantry</span>}
        </span>
        <span className="text-[13px] text-faint">
          {list.meals} {list.meals === 1 ? 'meal' : 'meals'} planned
        </span>
      </div>
      <p className="mx-0.5 mb-1 text-[12.5px] text-faint">Tap anything you already have to mark it in the pantry.</p>

      {list.items.length === 0 && (
        <div className="card mt-3 p-4 text-sm text-muted">
          Nothing yet.{' '}
          <Link to="/plan" className="font-semibold text-brand">
            Plan some dinners
          </Link>{' '}
          and the list fills itself.
        </div>
      )}

      {byAisle(list.items, aisles).map(([aisle, items]) => (
        <section key={aisle}>
          <h2 className="section-label mx-0.5 mt-4 mb-2">{aisle}</h2>
          <ul className="card divide-y divide-[#EFEAE0]">
            {items.map((i) => (
              <li key={i.id} className="flex items-center">
                <button
                  type="button"
                  onClick={() => patch.mutate({ id: i.id, in_pantry: !i.in_pantry })}
                  className="flex min-w-0 flex-1 items-baseline gap-2 px-3.5 py-3 text-left"
                  title={i.used_in.length ? `For ${i.used_in.join(', ')}` : undefined}
                >
                  <span className={`text-sm ${i.in_pantry ? 'text-faint line-through' : 'font-medium'}`}>{i.name}</span>
                  <span className="truncate text-[12.5px] text-faint">
                    {i.in_pantry ? '· in pantry' : i.amount && `· ${i.amount}`}
                  </span>
                </button>
                {i.manual && (
                  <button
                    type="button"
                    aria-label={`Remove ${i.name}`}
                    onClick={() => remove.mutate(i.id)}
                    className="px-3.5 text-lg text-faint"
                  >
                    ×
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}

      <form
        className="mt-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (newItem.trim()) add.mutate(newItem.trim(), { onSuccess: () => setNewItem('') })
        }}
      >
        <input
          placeholder="Add something else (paper towels…)"
          value={newItem}
          onChange={(e) => setNewItem(e.target.value)}
          className="min-w-0 flex-1"
        />
        <button disabled={add.isPending} className="btn h-10 rounded-[10px] border border-line-strong bg-white text-sm">
          Add
        </button>
      </form>
      <ErrorText error={add.error ?? rebuild.error} />

      {toBuy.length > 0 && (
        <Link to="/shop" className="btn-primary mt-5 w-full">
          Start shopping
        </Link>
      )}
    </>
  )
}
