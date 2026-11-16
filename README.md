# Plenty

Plan the week, shop once, stay under the food budget. A meal planner that turns saved recipes into
one priced grocery list and tracks groceries and eating out against one pay-period budget.

FastAPI + React PWA in one Docker image. See `CLAUDE.md` for the stack, commands and phases.

## Run locally

```sh
docker compose up -d
cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload --port 8765
cd web && npm install && npm run dev    # http://localhost:5173
```
