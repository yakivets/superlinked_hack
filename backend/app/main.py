from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import settings
from app.inference import get_router
from app.store import Store

app = FastAPI(title="Meeting Notetaker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.on_event("startup")
def startup():
    if not hasattr(app.state, "store"):
        app.state.store = Store(settings.db_path)
    if not hasattr(app.state, "router"):
        app.state.router = get_router()


@app.get("/healthz")
def healthz():
    return {"ok": True}
