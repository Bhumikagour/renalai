import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.core import imaging_service

logger = logging.getLogger("renalai.imaging_router")
router = APIRouter(prefix="/imaging", tags=["imaging"])


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    modality: str = Form(...),
    patient_ref: str | None = Form(None),
):
    content = await file.read()
    try:
        result = imaging_service.process_imaging_upload(
            file.filename or "upload", content, modality.lower(), patient_ref
        )
        return result
    except imaging_service.ImagingValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Imaging upload failed")
        raise HTTPException(status_code=500, detail=f"Imaging pipeline failed: {e}")


@router.get("/history")
def history(patient_ref: str | None = None):
    return imaging_service.get_result_history(patient_ref)
