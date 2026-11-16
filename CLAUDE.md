# Plenty

Personal meal planner and food budget. Plan dinners from saved recipes, merge them into one priced
grocery list, and keep all food spending (groceries + eating out) under $200 per two-week pay
period. Built for one household first; may merge into Buoy (`~/code/pers/buoy-app`) later.

Full brief: the build plan the owner wrote (not in repo). Visual spec: `design/mockups/` (open
`index.html`). Palette and copy come from there.

## Household facts (drive the domain logic)

- Owner every day; three kids from **Wed dinner to Sat lunch**. Kid days cook 2 dinners + 1 night out.
- Budget: **$200 per pay period**, groceries and eating out combined. Payday every 14 days, anchored
  on **2026-11-06**. Budgets reset on payday, not Monday.
- Stores: **Food Lion, Walmart**. Neither has a price API: prices come from receipts only.
  **Never scrape store websites.**
- Phone: Android Pixel, installed PWA, share sheet via `share_target`.

## Stack (mirrors Buoy, keep it that way)

- `backend/`: FastAPI, Python 3.12, SQLAlchemy 2 + Alembic, Postgres via psycopg 3, Pydantic v2 +
  pydantic-settings (`PLENTY_*` env vars, see `backend/.env.example`). uv, ruff, pytest.
- `web/`: React 19 + TS + Vite, Tailwind 4, React Router, TanStack Query, openapi-fetch with types
  generated from the FastAPI spec. oxlint + prettier.
- PWA is hand-rolled like Buoy (no vite-plugin-pwa): `web/public/manifest.webmanifest` + `sw.js`.
- One Docker image: Vite build served by FastAPI from the same origin; `alembic upgrade head` on start.
- Render free tier (`render.yaml`, deploys `dev`), Postgres on Neon (project `plenty`).
- Later: Anthropic SDK (recipe/receipt extraction, phase 1/2), object storage for photos (bytea to
  start), USDA FoodData Central (phase 5).

## Layout and the Buoy-merge rules

- `backend/meal/`: pure domain package (parser, units, budget math, optimizer). **No FastAPI or
  SQLAlchemy imports.** Pure functions with unit tests.
- `backend/app/`: web layer. `api/` routers, `models.py`, `db.py` (config + engine).
- Auth tables (`user`, `session`) are Buoy's, in `public`, same names. On a merge Buoy's win.
- **Every meal table lives in the `meal` Postgres schema** (`__table_args__ = {"schema": MEAL_SCHEMA}`).
- Food spending gets stored as plain transactions (date, amount, place, category).
- Money is integer cents. Weekdays follow Python `date.weekday()` (Mon=0..Sun=6), in API and web.

## Commands

```sh
docker compose up -d                      # Postgres 17 on localhost:5433 (dbs: plenty, plenty_test)

cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8765
uv run pytest                             # needs compose Postgres; uses plenty_test
uv run ruff check . && uv run ruff format .
uv run alembic revision --autogenerate -m "..."   # then read the file; `uv run alembic check` must pass

cd web
npm install
npm run dev                               # :5173, proxies /api to :8765
npm run gen:api                           # regenerate src/api/schema.d.ts (backend must be running)
npm run lint && npm run build
npm run format

docker build -t plenty .                  # what Render builds
```

## Conventions

- Tests: real Postgres, each test in a rolled-back transaction (`tests/conftest.py`). API tests use
  the `client` / `new_client` fixtures. Domain tests import from `meal` only.
- After any API change: run the backend and `npm run gen:api`; commit `schema.d.ts`.
- Every automatic match (recipe text or receipt line to a canonical Ingredient) gets a confirm step,
  and corrections are stored and reused.
- Log model usage from the first Claude call; cache every extraction.
- Secrets only in env vars. Add new ones to `.env.example` and `render.yaml` (`sync: false`).
- Commit after each working feature, on `dev`.
- UI copy and layout follow `design/mockups/`. Tokens are in `web/src/index.css` (`@theme`).

## Share target (non-obvious)

Android POSTs shares (multipart: title, text, url, images) to `/share-target`. The service worker
intercepts it, parks the data in Cache Storage (`share-inbox`), and redirects to `/share`, which
reads it same-origin with the session cookie. If the worker isn't active yet, FastAPI answers
`POST /share-target` with a redirect to `/share?missed=1`. `sw.js` is served `no-cache`.

## Phases (one at a time; show a short plan and wait for OK before each)

- [x] **0. Setup**: scaffold, schema, deploy, installable PWA with share target.
- [ ] **1. Plan and list**: recipe box (share sheet, link, text, screenshot -> extraction -> confirm
      screen), planner with kid and solo days, merged list by aisle, shop mode.
      Done: a real kid week planned and shopped in one trip.
- [ ] **2. Budget and price book**: receipt photo -> line items -> Products + PriceObservations,
      one-tap eating-out log, pay-period budget bar with pace. Done: list estimate within 10% of receipt.
- [ ] **3. Optimizer**: unit price, package rounding, leftovers, swaps by savings, second store only
      above a threshold.
- [ ] **4. AI planner**: a pay period under budget from recipes, pantry, price book.
- [ ] **5. Macros (v2)**: USDA matching, owner's daily calories and protein.
- [ ] **6. Reach**: Instacart hand-off, other households, merge into Buoy.

Nothing past phase 2 starts until phase 2 passes.

## Data model (target; only `household` exists so far)

Household, PayPeriod (computed by `meal.schedule.pay_period`), Recipe, Ingredient (canonical),
RecipeIngredient, PlanEntry, Product, PriceObservation, GroceryListItem, Receipt, PantryItem,
FoodSpend. Recipe text and receipt text both map to a canonical Ingredient.
