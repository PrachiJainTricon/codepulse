"""
FastAPI application for the CodePulse REST API.

Start with:
    uvicorn codepulse.api.server:app --reload
or via the CLI:
    codepulse ui
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from codepulse.api.routes.analysis import router as analysis_router
from codepulse.api.routes.repos import router as repos_router
from codepulse.api.routes.graph import router as graph_router
from codepulse.api.routes.chat import router as chat_router

app = FastAPI(
    title="CodePulse",
    description="Code intelligence API — blast-radius analysis and risk scoring.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router, prefix="/analysis", tags=["analysis"])
app.include_router(repos_router,    prefix="/repos",    tags=["repos"])
app.include_router(graph_router,    prefix="/graph",    tags=["graph"])
app.include_router(chat_router,     prefix="/chat",     tags=["chat"])


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
