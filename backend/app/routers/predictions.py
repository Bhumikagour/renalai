import logging
from fastapi import APIRouter, HTTPException

from app.schemas.prediction import PredictionRequest, PredictionResponse
from app.core import explain

logger = logging.getLogger("renalai.predictions")
router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/schema")
def get_schema():
    """Single source of truth for what fields the model expects -- the frontend
    should build its form from this, not a hardcoded duplicate list."""
    if not explain.model_is_ready():
        raise HTTPException(
            status_code=503,
            detail=f"Model not loaded: {explain.get_load_error()}. Core prediction is unavailable.",
        )
    return explain.get_feature_schema()


@router.post("", response_model=PredictionResponse)
def predict(payload: PredictionRequest):
    if not explain.model_is_ready():
        raise HTTPException(
            status_code=503,
            detail=f"Prediction model failed to load: {explain.get_load_error()}. "
                   f"This is a core-system failure -- check model_artifacts/ was deployed correctly.",
        )
    try:
        result = explain.explain_prediction(payload.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Prediction failed")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")
