import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { useAuth, useHousehold } from './lib/hooks'
import type { Household } from './api/client'
import LoginPage from './pages/LoginPage'
import PlanPage from './pages/PlanPage'
import RecipePage from './pages/RecipePage'
import RecipesPage from './pages/RecipesPage'
import { EditRecipePage, ReviewDraftPage } from './pages/ReviewRecipePage'
import SetupPage from './pages/SetupPage'
import SharePage from './pages/SharePage'
import StubPage from './pages/StubPage'

// Icons and order from design/mockups (bottom nav).
const tabs = [
  { to: '/recipes', label: 'Recipes', icon: 'M4 19V5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2zM6 17h12' },
  {
    to: '/plan',
    label: 'Plan',
    icon: 'M6 4.5h12a2.5 2.5 0 0 1 2.5 2.5v11a2.5 2.5 0 0 1-2.5 2.5H6A2.5 2.5 0 0 1 3.5 18V7A2.5 2.5 0 0 1 6 4.5zM3.5 9h17M8 3v3M16 3v3',
  },
  { to: '/list', label: 'List', icon: 'M9 6h11M9 12h11M9 18h11M4 5.5l1 1 1.6-2M4 11.5l1 1 1.6-2M4 17.5l1 1 1.6-2' },
  {
    to: '/spending',
    label: 'Spending',
    icon: 'M6 6.5h12a2.5 2.5 0 0 1 2.5 2.5v7a2.5 2.5 0 0 1-2.5 2.5H6A2.5 2.5 0 0 1 3.5 16V9A2.5 2.5 0 0 1 6 6.5zM16 13h2.5',
  },
]

export default function App() {
  const { data: auth, error } = useAuth()
  if (error) return <p className="py-20 text-center text-rose-700">Can't reach Plenty. Check your connection.</p>
  if (!auth) return null
  if (!auth.user) return <LoginPage signupOpen={auth.signup_open} />
  return <SignedIn />
}

function SignedIn() {
  const { data: household, error } = useHousehold()
  if (error) return <p className="py-20 text-center text-rose-700">{error.message}</p>
  if (household === undefined) return null
  if (household === null) return <SetupPage />
  return (
    <Routes>
      {/* Full-screen flows with their own bottom bar */}
      <Route path="/recipes/review" element={<ReviewDraftPage />} />
      <Route path="/recipes/:id/edit" element={<EditRecipePage />} />
      <Route path="/setup" element={<SetupPage household={household} />} />
      <Route path="*" element={<Tabs household={household} />} />
    </Routes>
  )
}

function Tabs({ household }: { household: Household }) {
  return (
    <div className="mx-auto flex min-h-dvh max-w-xl flex-col">
      <main className="flex-1 px-4 pt-[max(1.1rem,env(safe-area-inset-top))] pb-28">
        <Routes>
          <Route path="/" element={<Navigate to="/plan" replace />} />
          <Route path="/plan" element={<PlanPage household={household} />} />
          <Route path="/recipes" element={<RecipesPage />} />
          <Route path="/recipes/:id" element={<RecipePage />} />
          <Route
            path="/list"
            element={<StubPage title="Grocery list" note="One merged list by aisle, plus shop mode, coming next." />}
          />
          <Route
            path="/spending"
            element={<StubPage title="Spending" note="Receipts, the eating-out log and budget pace land in phase 2." />}
          />
          <Route path="/share" element={<SharePage />} />
          <Route path="*" element={<Navigate to="/plan" replace />} />
        </Routes>
      </main>

      <nav className="fixed inset-x-0 bottom-0 border-t border-[#E7E1D7] bg-white pb-[env(safe-area-inset-bottom)]">
        <div className="mx-auto grid max-w-xl grid-cols-4">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              className={({ isActive }) =>
                `flex flex-col items-center gap-[3px] pt-2.5 pb-3 text-[11px] font-medium ${isActive ? 'text-brand' : 'text-faint'}`
              }
            >
              <svg
                viewBox="0 0 24 24"
                className="h-[22px] w-[22px]"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.8}
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d={t.icon} />
              </svg>
              {t.label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
