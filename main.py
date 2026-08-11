from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.models.database import create_tables, SessionLocal
from app.services.seed import run_seed
from app.services.surveys_data import seed_surveys
from app.routers import auth, dashboard, users, cycles, evaluations, competencies, surveys, reminders


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    db = SessionLocal()
    try:
        run_seed(db)
        seed_surveys(db)
    finally:
        db.close()
    print("AVD 360 iniciado em http://localhost:8000")
    yield


app = FastAPI(
    title="AVD 360 | Grupo Gestao",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(cycles.router)
app.include_router(evaluations.router)
app.include_router(competencies.router)
app.include_router(surveys.router)
app.include_router(reminders.router)


@app.get("/")
async def root():
    return RedirectResponse("/dashboard", status_code=302)


@app.exception_handler(302)
async def redirect_handler(request: Request, exc):
    return RedirectResponse(url="/login", status_code=302)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


@app.get("/setup")
async def setup():
    from app.models.database import create_tables, SessionLocal
    from app.services.seed import run_seed
    from app.services.surveys_data import seed_surveys
    create_tables()
    db = SessionLocal()
    run_seed(db)
    seed_surveys(db)
    db.close()
    return {"status": "ok", "msg": "Setup concluido! Admin criado."}
