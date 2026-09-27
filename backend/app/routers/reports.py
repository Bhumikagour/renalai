import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.core import explain, pdf_service
from app.schemas.prediction import PredictionRequest

logger = logging.getLogger("renalai.reports_router")
router = APIRouter(prefix="/reports", tags=["reports"])


class ReportRequest(BaseModel):
    patient_name: str | None = None
    clinical_data: PredictionRequest
    doctor_notes: str | None = None


@router.post("/generate")
def generate_report(payload: ReportRequest):
    if not explain.model_is_ready():
        raise HTTPException(
            status_code=503,
            detail=f"Cannot generate report: prediction model not loaded ({explain.get_load_error()}).",
        )
    try:
        patient_dict = payload.clinical_data.model_dump()
        prediction_result = explain.explain_prediction(patient_dict)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Prediction step failed during report generation")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")

    try:
        pdf_bytes, report_id = pdf_service.generate_report_pdf(
            patient_name=payload.patient_name or "Not specified",
            patient_inputs=patient_dict,
            prediction_result=prediction_result,
            doctor_notes=payload.doctor_notes,
        )
    except pdf_service.PDFGenerationError as e:
        # PDF generation is independent -- a failure here must not look like a
        # prediction failure. Report it distinctly, keep the app alive.
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{report_id}.pdf"'},
    )
