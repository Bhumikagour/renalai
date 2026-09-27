import logging
from fastapi import APIRouter
from pydantic import BaseModel

from app.core import chat_service

logger = logging.getLogger("renalai.chat_router")
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    available: bool
    reply: str | None = None
    error: str | None = None


@router.get("/status")
def status():
    return {"available": chat_service.chat_is_configured()}


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    try:
        history = [{"role": m.role, "content": m.content} for m in payload.history]
        result = await chat_service.ask_assistant(payload.message, history)
        return ChatResponse(available=True, reply=result["reply"])
    except chat_service.ChatUnavailableError as e:
        # Graceful unavailable state -- never a 500, never a fake reply.
        return ChatResponse(available=False, error=str(e))
