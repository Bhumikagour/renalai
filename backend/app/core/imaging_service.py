"""
RenalAI Medical Imaging module.

CRITICAL: the structured CKD model (ckd_model_pipeline.joblib, trained on lab-value
data) CANNOT and does NOT classify images. There is no trained imaging model in this
project. This module implements the extensible pipeline architecture the spec asks
for -- upload, validation, preview, preprocessing, an inference-service interface,
confidence display, and a Grad-CAM integration point -- but returns clearly labeled
PROTOTYPE output, never a fabricated diagnostic result.

Wiring in a real trained imaging model later means implementing `run_inference()`
below to call that model; everything else (validation, preprocessing, storage,
result history) already works end-to-end.
"""
import io
import logging
import uuid
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from PIL import Image

from app.core import gradcam_service

logger = logging.getLogger("renalai.imaging")

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "imaging"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".dcm"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
ALLOWED_MODALITIES = {"ct", "mri", "usg"}

# In-memory result history for this MVP (no database yet -- see backend/app/models/).
# A real deployment must persist this in the MedicalImage table per the spec.
_RESULT_HISTORY: list[dict] = []


class ImagingValidationError(Exception):
    pass


def validate_upload(filename: str, content: bytes, modality: str) -> None:
    if modality not in ALLOWED_MODALITIES:
        raise ImagingValidationError(
            f"Unknown modality '{modality}'. Must be one of {sorted(ALLOWED_MODALITIES)}."
        )
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ImagingValidationError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if len(content) == 0:
        raise ImagingValidationError("Uploaded file is empty.")
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ImagingValidationError(f"File exceeds {MAX_FILE_SIZE_BYTES // (1024*1024)} MB limit.")
    if ext in (".png", ".jpg", ".jpeg"):
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()
        except Exception:
            raise ImagingValidationError("File could not be read as a valid image.")


def preprocess_image(content: bytes, target_size: tuple[int, int] = (224, 224)) -> np.ndarray:
    """Standard preprocessing any real imaging model would need: decode, resize,
    normalize. This runs for real (not stubbed) so the interface is genuinely wired,
    even though no model consumes its output yet."""
    img = Image.open(io.BytesIO(content)).convert("L")  # grayscale, typical for CT/MRI/USG
    img = img.resize(target_size)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return arr


def run_inference(preprocessed: np.ndarray, modality: str) -> dict:
    """
    PROTOTYPE INTERFACE ONLY.
    No trained imaging model exists in this project. This function is the exact
    integration point where a real model's `.predict()` call would go. It does
    NOT fabricate a diagnostic result -- it returns an explicit prototype/no-model
    state so the frontend can label it honestly.
    """
    return {
        "status": "prototype_no_model",
        "modality": modality,
        "confidence": None,
        "predicted_class": None,
        "gradcam_available": False,
        "message": (
            "No trained medical imaging model is deployed in this project. The CSV-trained "
            "CKD model uses structured lab values only and cannot and does not analyze "
            "images. This response demonstrates the imaging pipeline architecture "
            "(upload -> validate -> preprocess -> inference interface -> result) with a "
            "placeholder result. Wiring in a real classifier requires a properly trained "
            "and validated imaging model plus an appropriate imaging dataset, which do not "
            "exist in this project."
        ),
    }


def process_imaging_upload(filename: str, content: bytes, modality: str, patient_ref: str | None = None) -> dict:
    validate_upload(filename, content, modality)

    image_id = str(uuid.uuid4())
    ext = Path(filename).suffix.lower()
    saved_path = UPLOAD_DIR / f"{image_id}{ext}"
    saved_path.write_bytes(content)

    try:
        preprocessed = preprocess_image(content)
        preprocessing_ok = True
        preprocessing_shape = list(preprocessed.shape)
    except Exception as e:
        logger.warning("Imaging preprocessing failed (non-fatal, DICOM or unusual format?): %s", e)
        preprocessing_ok = False
        preprocessing_shape = None

    inference_result = run_inference(
        preprocessed if preprocessing_ok else None, modality
    )

    # Grad-CAM only runs against real, decodable image bytes (PIL can't open DICOM
    # here), and only when preprocessing already proved the file is a valid image.
    if preprocessing_ok and ext in (".png", ".jpg", ".jpeg"):
        try:
            gradcam_result = gradcam_service.generate_gradcam(content)
        except Exception as e:
            logger.warning("Grad-CAM generation failed (non-fatal): %s", e)
            gradcam_result = {"available": False, "overlay_base64": None, "note": f"Grad-CAM failed: {e}"}
    else:
        gradcam_result = {
            "available": False,
            "overlay_base64": None,
            "note": "Grad-CAM currently only runs for PNG/JPEG uploads that preprocess successfully.",
        }
    inference_result["gradcam_available"] = bool(gradcam_result.get("available"))

    record = {
        "image_id": image_id,
        "modality": modality,
        "patient_ref": patient_ref,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "preprocessing_ok": preprocessing_ok,
        "preprocessing_shape": preprocessing_shape,
        "label": "Prototype Imaging Analysis Pipeline",
        "result": inference_result,
        "gradcam": gradcam_result,
    }
    _RESULT_HISTORY.append(record)
    return record


def get_result_history(patient_ref: str | None = None) -> list[dict]:
    if patient_ref:
        return [r for r in _RESULT_HISTORY if r.get("patient_ref") == patient_ref]
    return list(_RESULT_HISTORY)
