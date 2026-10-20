from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR
from app.database import Base, engine
from app import models  # noqa: F401 - imports register SQLAlchemy models
from app.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="FitBuddy API", description="Personalized workout plan generation, revisions, and tips.", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "service": "FitBuddy"}
