import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from db.database import engine
from db.models import Base
from db.seed import seed_rules
from api.routers import evaluate, rules, admin, ai


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    seed_rules()
    yield


app = FastAPI(title="Stand Mitigation Rules Engine", version="0.1.0", lifespan=lifespan)


app.include_router(evaluate.router, tags=["Evaluation"])
app.include_router(rules.router, tags=["Rules"])
app.include_router(admin.router, tags=["Admin"])
app.include_router(ai.router, tags=["AI"])

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse("static/index.html")
