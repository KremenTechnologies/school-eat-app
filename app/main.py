import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware

from .db import pool, init_schema, seed_developers
from .routes import router

_INDEX = Path(__file__).parent.parent / "templates" / "attendance-app.html"


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool.open()
    init_schema()
    seed_developers()
    yield
    # pool lives for the process lifetime; render kills the process on shutdown


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET"],
    https_only=bool(os.environ.get("RENDER")),
    same_site="lax",
)
app.include_router(router)


@app.get("/")
def index():
    return FileResponse(_INDEX)
