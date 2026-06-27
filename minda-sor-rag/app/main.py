import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.services.classifier import init_knowledge_base


@asynccontextmanager
async def lifespan(app: FastAPI):
    for d in (
        settings.UPLOAD_DIR,
        settings.RESULTS_DIR,
        settings.EXPORT_DIR,
        settings.CHROMA_DIR,
    ):
        os.makedirs(d, exist_ok=True)
    init_knowledge_base()
    yield


app = FastAPI(
    title="SOR Requirements Analyzer",
    version="1.0.0",
    description=(
        "Upload SOR PDFs → classify statements as Ask vs Requirement "
        "per INCOSE/ISO 29148"
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
