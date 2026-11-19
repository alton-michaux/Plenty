from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, grocery, household, plan, recipes
from app.db import config

app = FastAPI(title="Plenty", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if config.cookie_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


for router in (auth.router, household.router, recipes.router, plan.router, grocery.router):
    app.include_router(router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/share-target", include_in_schema=False)
def share_target_fallback():
    """The service worker normally answers Android share-sheet posts (web/public/sw.js).
    If it wasn't active yet, the post lands here: send the user on so they can share again."""
    return RedirectResponse("/share?missed=1", status_code=303)


# In production the API also serves the built web app, so everything is one origin.
if config.static_dir:
    static = Path(config.static_dir).resolve()
    app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def web_app(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        file = (static / path).resolve()
        if path and file.is_file() and static in file.parents:
            # The service worker must never be cached, or updates to it get stuck.
            headers = {"Cache-Control": "no-cache"} if path == "sw.js" else None
            return FileResponse(file, headers=headers)
        # Client-side routes (/plan, /list, /share, ...) all load the app shell
        return FileResponse(static / "index.html", headers={"Cache-Control": "no-cache"})
