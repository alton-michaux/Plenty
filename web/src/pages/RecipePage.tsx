import { Link, useNavigate, useParams } from 'react-router-dom'
import { ErrorText } from '../components/Field'
import { useDeleteRecipe, useRecipe } from '../lib/hooks'
import { formatAmount } from '../lib/units'

export default function RecipePage() {
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const { data: r, error } = useRecipe(id)
  const del = useDeleteRecipe()
  if (error) return <p className="py-10 text-center text-sm text-muted">{error.message}</p>
  if (!r) return null

  return (
    <>
      <Link to="/recipes" className="text-sm font-semibold text-brand">
        ‹ Recipes
      </Link>
      <h1 className="mt-2 text-[26px] leading-tight font-bold tracking-[-0.5px]">{r.title}</h1>
      <p className="mt-1 text-[13px] text-muted">
        {[r.minutes && `${r.minutes} min`, r.servings && `serves ${r.servings}`, ...r.tags].filter(Boolean).join(' · ')}
      </p>
      {r.image_id && (
        <img src={`/api/uploads/${r.image_id}`} alt="" className="mt-3 max-h-64 w-full rounded-2xl object-cover" />
      )}

      <h2 className="section-label mx-0.5 mt-5 mb-2">Ingredients · {r.lines.length}</h2>
      <ul className="card divide-y divide-[#EFEAE0]">
        {r.lines.map((l) => (
          <li key={l.id} className="flex gap-3 px-3.5 py-2.5 text-sm">
            <span className="w-[70px] flex-none font-semibold">{formatAmount(l.quantity, l.unit) || '–'}</span>
            <span className="flex-1">
              {l.name}
              {l.note && <span className="text-faint">, {l.note}</span>}
            </span>
          </li>
        ))}
      </ul>

      {r.steps.length > 0 && (
        <>
          <h2 className="section-label mx-0.5 mt-5 mb-2">Steps</h2>
          <ol className="card list-decimal space-y-2 py-3 pr-4 pl-9 text-sm leading-relaxed">
            {r.steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </>
      )}
      {r.source_url && (
        <a href={r.source_url} target="_blank" rel="noreferrer" className="mt-3 block truncate text-sm text-brand">
          Source: {r.source_url}
        </a>
      )}

      <div className="mt-6 flex gap-2.5">
        <Link to={`/recipes/${r.id}/edit`} className="btn h-12 flex-1 border border-line-strong bg-white text-ink">
          Edit
        </Link>
        <button
          type="button"
          className="btn h-12 border border-line-strong bg-white px-5 text-rose-700"
          disabled={del.isPending}
          onClick={() => {
            if (confirm(`Delete “${r.title}”? It also comes off any planned days.`))
              del.mutate(r.id, { onSuccess: () => navigate('/recipes', { replace: true }) })
          }}
        >
          Delete
        </button>
      </div>
      <ErrorText error={del.error} />
    </>
  )
}
