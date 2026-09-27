import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import predictions, ocr, reports, chat, imaging, location
from app.core import explain, chat_service, location_service, gradcam_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("renalai")

app = FastAPI(
    title="RenalAI API",
    description="AI-powered CKD clinical decision support -- prediction MVP",
    version="0.2.0-mvp",
)

# CORS. Hardcoding localhost breaks every deployed frontend, so the allowlist is
# environment-driven:
#   FRONTEND_URL          comma-separated exact origins (default: local dev)
#   ALLOWED_ORIGIN_REGEX  a pattern, used by the Render blueprint so the two
#                         services do not need a circular `fromService` link
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
allowed_origins = [x.strip() for x in frontend_url.split(",") if x.strip()]
allowed_origin_regex = os.getenv("ALLOWED_ORIGIN_REGEX") or None

logger.info("CORS exact origins=%s regex=%s", allowed_origins, allowed_origin_regex)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predictions.router)
app.include_router(ocr.router)
app.include_router(reports.router)
app.include_router(chat.router)
app.include_router(imaging.router)
app.include_router(location.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": explain.model_is_ready(),
        "model_load_error": None if explain.model_is_ready() else explain.get_load_error(),
        "optional_services": {
            "ai_chatbot": chat_service.chat_is_configured(),
            "location_search": location_service.location_is_configured(),
            "gradcam": gradcam_service.gradcam_is_configured(),
        },
    }


@app.get("/")
def root():
    return {"service": "RenalAI API", "docs": "/docs", "health": "/health"}
