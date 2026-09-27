import logging
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.core import ocr_service

logger = logging.getLogger("renalai.ocr_router")
router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("/scan")
async def scan_document(file: UploadFile = File(...)):
    """
    Upload a medical document (PNG/JPG/JPEG/PDF), extract lab values via OCR.
    Response ALWAYS requires human confirmation downstream -- values here are
    never auto-submitted to the prediction endpoint.
    """
    content = await file.read()
    try:
        result = ocr_service.process_ocr_upload(file.filename or "upload", content)
        return result
    except ocr_service.OCRValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("OCR scan failed")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {e}")
