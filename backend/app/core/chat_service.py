"""
RenalAI Kidney Health AI Assistant.

Provider is environment-configured (ANTHROPIC_API_KEY). If the key is missing or the
API call fails for any reason, the service returns a structured "unavailable" state --
it never fabricates a response and never crashes the request.

The assistant is explicitly instructed to never present itself as a doctor and to
always include safety framing, enforced both in the system prompt and as a
belt-and-suspenders disclaimer appended server-side.
"""
import logging
import os
import httpx

logger = logging.getLogger("renalai.chat")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("RENALAI_CHAT_MODEL", "claude-sonnet-4-6")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You are the RenalAI Kidney Health Assistant, an educational AI embedded in a \
chronic kidney disease (CKD) screening platform.

You may:
- Explain a patient's CKD screening prediction result and what the contributing lab \
values generally mean.
- Explain common kidney-related laboratory values (creatinine, GFR, BUN, albumin, etc.) \
in plain language.
- Answer general educational questions about CKD, its risk factors, and stages.
- Provide general lifestyle education (diet, hydration, exercise) relevant to kidney health.
- Explain medical terminology in plain language.

You must NEVER:
- Present yourself as a doctor, nurse, or any licensed medical professional.
- Provide an individualized diagnosis, prescribe or adjust medication, or tell someone to \
stop/start a specific treatment.
- Contradict or override a treating clinician's guidance.

Always keep responses grounded, calm, and factual. If a question requires clinical \
judgment about a specific person's care, say so plainly and recommend they consult their \
doctor or nephrologist. Keep responses concise (a few short paragraphs at most)."""

SAFETY_FOOTER = (
    "\n\n---\n*RenalAI's assistant provides general educational information only and is "
    "not a substitute for professional medical advice. Please consult a licensed "
    "physician or nephrologist for decisions about your care.*"
)


class ChatUnavailableError(Exception):
    pass


def chat_is_configured() -> bool:
    return bool(ANTHROPIC_API_KEY)


async def ask_assistant(message: str, conversation_history: list[dict] | None = None) -> dict:
    """
    Returns {"reply": str, "model": str} on success.
    Raises ChatUnavailableError on missing key or any upstream failure -- callers
    (the router) turn this into a graceful "unavailable" response, never a crash
    and never a fabricated reply.
    """
    if not chat_is_configured():
        raise ChatUnavailableError(
            "The AI assistant is not configured (missing ANTHROPIC_API_KEY). "
            "Core CKD prediction is unaffected."
        )

    messages = (conversation_history or []) + [{"role": "user", "content": message}]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                ANTHROPIC_URL,
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": ANTHROPIC_MODEL,
                    "max_tokens": 600,
                    "system": SYSTEM_PROMPT,
                    "messages": messages,
                },
            )
        if resp.status_code != 200:
            logger.error("Anthropic API error %s: %s", resp.status_code, resp.text[:500])
            raise ChatUnavailableError(f"AI assistant upstream error (status {resp.status_code}).")

        data = resp.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        reply = "\n".join(text_blocks).strip()
        if not reply:
            raise ChatUnavailableError("AI assistant returned an empty response.")

        return {"reply": reply + SAFETY_FOOTER, "model": ANTHROPIC_MODEL}

    except httpx.RequestError as e:
        logger.error("Anthropic API request failed: %s", e)
        raise ChatUnavailableError(f"Could not reach the AI assistant service: {e}")
