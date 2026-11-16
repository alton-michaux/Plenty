export function PageHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <header className="pb-1.5">
      <h1 className="text-[26px] font-bold tracking-[-0.5px]">{title}</h1>
      {sub && <p className="mt-0.5 text-[13px] text-muted">{sub}</p>}
    </header>
  )
}

export default function StubPage({ title, note }: { title: string; note: string }) {
  return (
    <>
      <PageHeader title={title} />
      <div className="card mt-3 p-4 text-sm text-muted">{note}</div>
    </>
  )
}
