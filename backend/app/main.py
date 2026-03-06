"""
Interview Copilot – FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.services.transcription import close_transcription_client
from app.api.ws_interview import router as ws_router
from app.api.routes_session import router as session_router
from app.api.routes_context import router as context_router
from app.api.routes_evaluation import router as eval_router

logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_transcription_client()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)
app.include_router(session_router)
app.include_router(context_router)
app.include_router(eval_router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}
