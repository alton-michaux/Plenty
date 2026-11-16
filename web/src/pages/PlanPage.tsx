import { Link } from 'react-router-dom'
import type { Household } from '../api/client'
import { daysUntil, money0, shortDate } from '../lib/format'
import { DAYS, kidDays, kidWindowLabel } from '../lib/week'
import { PageHeader } from './StubPage'

export default function PlanPage({ household: h }: { household: Household }) {
  const p = h.period
  const toPayday = daysUntil(p.next_payday)
  const planned = 0 // filled in by the planner in phase 1
  const kids = kidDays(h)
  // Solo days in order, starting the day after the kids leave
  const soloDays = [1, 2, 3, 4, 5, 6, 7].map((i) => (kids.at(-1)! + i) % 7).filter((d) => !kids.includes(d))

  return (
    <>
      <PageHeader
        title="This pay period"
        sub={`${shortDate(p.start)} – ${shortDate(p.end)}${h.kids ? ` · kids here ${DAYS[kids[0]]}–${DAYS[kids.at(-1)!]}` : ''}`}
      />

      <div className="card mt-2 mb-1.5 p-3.5">
        <div className="flex items-baseline justify-between">
          <span className="section-label">Pay-period budget</span>
          <span className="text-[13px] text-faint">
            {toPayday === 1 ? 'Payday tomorrow' : `${toPayday} days to payday`}
          </span>
        </div>
        <div className="mt-2.5 h-[9px] overflow-hidden rounded-full bg-line">
          <div
            className="h-full rounded-full bg-brand"
            style={{ width: `${Math.min(100, (planned / h.budget_cents) * 100)}%` }}
          />
        </div>
        <div className="mt-2 flex items-baseline justify-between">
          <span className="text-sm">
            <strong className="text-brand">{money0(planned)}</strong> planned of {money0(h.budget_cents)}
          </span>
          <span className="text-[13px] text-muted">
            Day {p.day} of {p.length}
          </span>
        </div>
      </div>

      {h.kids > 0 && <Section label={`Kids here · ${kidWindowLabel(h)}`} aside="cook 2, out 1" />}
      <Section label={`Just me · ${soloDays.map((d) => DAYS[d]).join(', ')}`} aside="cheap & easy" />

      <div className="card mt-3 p-4 text-sm text-muted">
        Nothing planned yet. Recipes and the week planner arrive in phase 1.
      </div>

      <p className="mt-6 text-center text-sm">
        <Link to="/setup" className="font-semibold text-brand">
          Edit household
        </Link>
      </p>
    </>
  )
}

function Section({ label, aside }: { label: string; aside: string }) {
  return (
    <h2 className="section-label mx-0.5 mt-4 mb-2 flex items-baseline justify-between">
      <span>{label}</span>
      <span className="font-semibold tracking-normal text-faint normal-case">{aside}</span>
    </h2>
  )
}
