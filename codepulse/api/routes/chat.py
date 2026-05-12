"""
POST /chat  —  ask a question about the indexed codebase.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from codepulse.agents.chat_agent import answer

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    symbol_hint: str | None = None


class ChatResponse(BaseModel):
    answer: str


@router.post("/", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    """Answer a natural-language question about the codebase."""
    reply = answer(body.question, symbol_hint=body.symbol_hint)
    return ChatResponse(answer=reply)
