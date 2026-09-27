"""
RenalAI OCR service.

Pipeline: upload -> OCR (tesseract) -> regex-based lab-value extraction ->
return extracted values WITH confidence + raw context, so the frontend can
require manual confirmation before anything reaches the prediction form.

Per spec: OCR output is NEVER treated as medically correct automatically.
"""
import io
import json
import logging
import re
import uuid
from pathlib import Path

import pytesseract
from PIL import Image

logger = logging.getLogger("renalai.ocr")

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "model_artifacts" / "feature_schema.json"
_schema = json.load(open(SCHEMA_PATH))
NUMERIC_FEATURES = _schema["numeric_features"]
CATEGORICAL_FEATURES = _schema["categorical_features"]
CATEGORICAL_ALLOWED = _schema["categorical_allowed_values"]

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "ocr"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB

# Lab-value patterns: label variants -> (schema_key, regex, unit hint)
# Patterns are intentionally permissive on spacing/colons/units since real scanned
# lab reports vary a lot, but each capture group is a plain number/word we validate after.
LAB_PATTERNS = {
    "age": r"\bage\b[:\s]*([0-9]{1,3})",
    "bp": r"\b(?:blood pressure|bp)\b[:\s]*([0-9]{2,3})",
    "sg": r"\b(?:specific gravity|sg)\b[:\s]*([0-9]\.[0-9]{2,3})",
    "al": r"\balbumin\b[:\s]*([0-9](?:\.[0-9])?)",
    "su": r"\bsugar\b[:\s]*([0-9](?:\.[0-9])?)",
    "bgr": r"\b(?:blood glucose|bgr|glucose)\b[:\s(a-z)]*([0-9]{2,3})",
    "bu": r"\b(?:blood urea|bu)\b[:\s]*([0-9]{1,3}(?:\.[0-9])?)",
    "sc": r"\b(?:serum creatinine|creatinine|sc)\b[:\s]*([0-9]{1,2}\.?[0-9]?)",
    "sod": r"\b(?:sodium|sod|na)\b[:\s]*([0-9]{2,3})",
    "pot": r"\b(?:potassium|pot|k\+?)\b[:\s]*([0-9]{1,2}\.[0-9])",
    "hemo": r"\b(?:hemoglobin|haemoglobin|hemo|hb)\b[:\s]*([0-9]{1,2}\.[0-9])",
    "pcv": r"\b(?:packed cell volume|pcv|hematocrit)\b[:\s]*([0-9]{2})",
    "wc": r"\b(?:white blood cell|wbc|wc)\b[:\s]*([0-9]{3,5})",
    "rc": r"\b(?:red blood cell count|rbc count|rc)\b[:\s]*([0-9]\.[0-9])",
}

CATEGORICAL_PATTERNS = {
    "htn": r"\bhypertension\b[:\s]*(yes|no|present|absent)",
    "dm": r"\b(?:diabetes|dm)\b[:\s]*(yes|no|present|absent)",
    "cad": r"\b(?:coronary artery disease|cad)\b[:\s]*(yes|no|present|absent)",
    "appet": r"\bappetite\b[:\s]*(good|poor)",
    "pe": r"\b(?:pedal edema|pe)\b[:\s]*(yes|no|present|absent)",
    "ane": r"\banemia\b[:\s]*(yes|no|present|absent)",
    "rbc": r"\bred blood cells?\b[:\s]*(normal|abnormal)",
    "pc": r"\bpus cells?\b[:\s]*(normal|abnormal)",
    "pcc": r"\bpus cell clumps?\b[:\s]*(present|notpresent|absent)",
    "ba": r"\bbacteria\b[:\s]*(present|notpresent|absent)",
}

_YES_LIKE = {"yes", "present"}
_NO_LIKE = {"no", "absent", "notpresent"}

# Plausible physiological ranges used ONLY to flag suspicious OCR extractions for
# extra human scrutiny (e.g. a dropped decimal point turning 2.1 into 21) -- never
# to silently "correct" a value. Ranges are intentionally generous (not clinical
# cutoffs) so we flag only genuinely implausible OCR artifacts.
PLAUSIBLE_RANGES = {
    "age": (0, 120), "bp": (40, 220), "sg": (1.000, 1.035), "al": (0, 5), "su": (0, 5),
    "bgr": (30, 700), "bu": (2, 300), "sod": (100, 170),
    "pot": (1.5, 9), "hemo": (2, 20), "pcv": (9, 60), "wc": (1000, 30000), "rc": (1, 8),
    "sc": (0.1, 15),  # tighter than a theoretical ESRD max, to catch dropped-decimal OCR errors
}


class OCRValidationError(Exception):
    pass


def validate_upload(filename: str, content: bytes) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise OCRValidationError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if len(content) == 0:
        raise OCRValidationError("Uploaded file is empty.")
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise OCRValidationError(f"File exceeds {MAX_FILE_SIZE_BYTES // (1024*1024)} MB limit.")
    # Magic-byte sanity check so a renamed non-image/pdf file doesn't get processed
    if ext == ".pdf":
        if not content[:5] == b"%PDF-":
            raise OCRValidationError("File has a .pdf extension but is not a valid PDF.")
    else:
        if not (content[:3] == b"\xff\xd8\xff" or content[:8] == b"\x89PNG\r\n\x1a\n"):
            raise OCRValidationError("File extension does not match its actual image content.")


def _images_from_upload(filename: str, content: bytes) -> list[Image.Image]:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        import fitz  # PyMuPDF
        images = []
        doc = fitz.open(stream=content, filetype="pdf")
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)
        doc.close()
        return images
    else:
        return [Image.open(io.BytesIO(content))]


def extract_text(filename: str, content: bytes) -> str:
    images = _images_from_upload(filename, content)
    full_text = []
    for img in images:
        if img.mode != "L":
            img = img.convert("L")
        text = pytesseract.image_to_string(img)
        full_text.append(text)
    return "\n".join(full_text)


def parse_lab_values(raw_text: str) -> dict:
    """Regex-extract lab values from OCR'd text. Every field returned includes the
    raw matched snippet as evidence, so a human can sanity-check before confirming."""
    text_lower = raw_text.lower()
    extracted = {}

    for key, pattern in LAB_PATTERNS.items():
        m = re.search(pattern, text_lower)
        if m:
            try:
                value = float(m.group(1))
            except ValueError:
                continue
            confidence = "medium"
            flag = None
            lo, hi = PLAUSIBLE_RANGES.get(key, (None, None))
            if lo is not None and not (lo <= value <= hi):
                confidence = "low"
                flag = (
                    f"Value {value} is outside the typical range ({lo}-{hi}) for this field. "
                    f"OCR sometimes drops decimal points on scanned reports -- please verify "
                    f"against the original document."
                )
            extracted[key] = {
                "value": value,
                "matched_text": m.group(0).strip(),
                "confidence": confidence,
                "flag": flag,
            }

    for key, pattern in CATEGORICAL_PATTERNS.items():
        m = re.search(pattern, text_lower)
        if m:
            raw_val = m.group(1)
            if key in ("appet",):
                normalized = raw_val
            elif key in ("rbc", "pc"):
                normalized = raw_val
            elif key in ("pcc", "ba"):
                normalized = "present" if raw_val in _YES_LIKE else "notpresent"
            else:
                normalized = "yes" if raw_val in _YES_LIKE else "no"

            allowed = CATEGORICAL_ALLOWED.get(key, [])
            if allowed and normalized not in allowed:
                continue
            extracted[key] = {
                "value": normalized,
                "matched_text": m.group(0).strip(),
                "confidence": "medium",
            }

    return extracted


def process_ocr_upload(filename: str, content: bytes) -> dict:
    validate_upload(filename, content)

    doc_id = str(uuid.uuid4())
    saved_path = UPLOAD_DIR / f"{doc_id}{Path(filename).suffix.lower()}"
    saved_path.write_bytes(content)

    try:
        raw_text = extract_text(filename, content)
    except Exception as e:
        logger.exception("OCR text extraction failed")
        raise OCRValidationError(f"OCR failed to process this file: {e}")

    if not raw_text.strip():
        return {
            "document_id": doc_id,
            "raw_text": "",
            "extracted_fields": {},
            "warning": "No readable text was found in this document. It may be a low-quality "
                       "scan, a blank page, or an unsupported layout. Please enter values manually.",
        }

    extracted = parse_lab_values(raw_text)
    all_fields = set(NUMERIC_FEATURES) | set(CATEGORICAL_FEATURES)
    found_count = len(extracted)

    return {
        "document_id": doc_id,
        "raw_text": raw_text.strip(),
        "extracted_fields": extracted,
        "fields_found": found_count,
        "fields_total": len(all_fields),
        "warning": (
            None if found_count > 0 else
            "Text was extracted but no recognized lab values were matched. "
            "Please review the raw text and enter values manually."
        ),
    }
