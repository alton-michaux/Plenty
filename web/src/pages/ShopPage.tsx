import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Household } from '../api/client'
import { useAisles, useList, useListActions } from '../lib/hooks'
import { byAisle } from '../lib/list'

const STORE_KEY = 'plenty.store'

/** In-store checklist: big tap targets, works on a weak signal (see useList / useListActions). */
export default function ShopPage({ household }: { household: Household }) {
  const stores = household.stores ?? []
  const navigate = useNavigate()
  const { data: list } = useList()
  const { data: aisles = [] } = useAisles()
  const { patch } = useListActions()
  const [online, setOnline] = useState(navigator.onLine)
  const [store, setStore] = useState(() => {
    try {
      return localStorage.getItem(STORE_KEY) ?? stores[0] ?? ''
    } catch {
      return stores[0] ?? ''
    }
  })

  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])

  if (!list) return null
  const items = list.items.filter((i) => !i.in_pantry)
  const inCart = items.filter((i) => i.checked).length

  return (
    <div className="mx-auto flex min-h-dvh max-w-xl flex-col">
      <header className="sticky top-0 z-10 border-b border-[#EAE4DA] bg-white px-4 pt-[max(0.875rem,env(safe-area-inset-top))] pb-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-bold">
            Shopping
            {stores.length > 0 && (
              <>
                {' · '}
                <select
                  aria-label="Store"
                  value={store}
                  onChange={(e) => {
                    setStore(e.target.value)
                    try {
                      localStorage.setItem(STORE_KEY, e.target.value)
                    } catch {
                      /* ignore */
                    }
                  }}
                  className="h-auto border-0 bg-transparent p-0 text-lg font-bold text-brand focus:ring-0"
                >
                  {stores.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </>
            )}
          </h1>
          <span className="text-sm text-muted">
            {inCart} in cart · {items.length - inCart} to go
          </span>
        </div>
        <div className="mt-2.5 h-2 overflow-hidden rounded-full bg-line">
          <div
            className="h-full rounded-full bg-brand transition-all"
            style={{ width: `${items.length ? (inCart / items.length) * 100 : 0}%` }}
          />
        </div>
        {!online && (
          <p className="mt-2 text-xs font-medium text-amber-dark">Offline: check-offs will sync when you're back.</p>
        )}
      </header>

      <main className="flex-1 px-4 pb-4">
        {byAisle(items, aisles).map(([aisle, xs]) => (
          <section key={aisle}>
            <h2 className="section-label mx-0.5 mt-4 mb-2">{aisle}</h2>
            <ul className="card divide-y divide-[#EFEAE0]">
              {xs.map((i) => (
                <li key={i.id}>
                  <button
                    type="button"
                    onClick={() => patch.mutate({ id: i.id, checked: !i.checked })}
                    className="flex min-h-[60px] w-full items-center gap-3.5 px-4 py-3 text-left"
                  >
                    <span
                      className={`flex h-7 w-7 flex-none items-center justify-center rounded-full border-2 ${
                        i.checked ? 'border-brand bg-brand text-white' : 'border-line-strong'
                      }`}
                    >
                      {i.checked && (
                        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={3}>
                          <path d="M5 12l5 5 9-10" />
                        </svg>
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className={`block text-[16px] ${i.checked ? 'text-faint line-through' : 'font-medium'}`}>
                        {i.name}
                      </span>
                      {i.amount && <span className="text-[13px] text-muted">{i.amount}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </main>

      <div className="sticky bottom-0 border-t border-[#EAE4DA] bg-white px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <button type="button" className="btn-primary w-full" onClick={() => navigate('/list')}>
          {inCart === items.length && items.length > 0 ? 'Done shopping' : 'Back to list'}
        </button>
      </div>
    </div>
  )
}
