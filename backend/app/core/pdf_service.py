"""
RenalAI PDF report service.
Generates a downloadable clinical report for a single prediction.
Independent module: failures here must never take down the prediction API.
"""
import io
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

logger = logging.getLogger("renalai.pdf")

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

PRIMARY = HexColor("#0E7C86")
INK = HexColor("#101826")
INK_SOFT = HexColor("#4B5768")
RISK_COLORS = {"LOW": HexColor("#1E9E6B"), "MEDIUM": HexColor("#D98E04"), "HIGH": HexColor("#C4432B")}

CLINICAL_LABELS = {
    "age": "Age", "bp": "Blood pressure", "sg": "Specific gravity", "al": "Albumin",
    "su": "Sugar", "rbc": "Red blood cells", "pc": "Pus cells", "pcc": "Pus cell clumps",
    "ba": "Bacteria", "bgr": "Blood glucose (random)", "bu": "Blood urea",
    "sc": "Serum creatinine", "sod": "Sodium", "pot": "Potassium", "hemo": "Hemoglobin",
    "pcv": "Packed cell volume", "wc": "White blood cell count", "rc": "Red blood cell count",
    "htn": "Hypertension", "dm": "Diabetes mellitus", "cad": "Coronary artery disease",
    "appet": "Appetite", "pe": "Pedal edema", "ane": "Anemia",
}


class PDFGenerationError(Exception):
    pass


def _build_qr_image(report_id: str) -> RLImage:
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(f"RenalAI-Report:{report_id}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="#101826", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return RLImage(buf, width=22 * mm, height=22 * mm)


def generate_report_pdf(
    patient_name: str,
    patient_inputs: dict,
    prediction_result: dict,
    doctor_notes: str | None = None,
) -> tuple[bytes, str]:
    """Returns (pdf_bytes, report_id). Raises PDFGenerationError on failure --
    callers must catch this and degrade gracefully rather than crash the app."""
    try:
        report_id = f"RAI-{uuid.uuid4().hex[:10].upper()}"
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        risk = prediction_result.get("risk_category", "LOW")
        risk_color = RISK_COLORS.get(risk, INK)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "RTitle", parent=styles["Title"], textColor=PRIMARY, fontSize=20, spaceAfter=2,
        )
        subtitle_style = ParagraphStyle(
            "RSubtitle", parent=styles["Normal"], textColor=INK_SOFT, fontSize=9, spaceAfter=14,
        )
        h2 = ParagraphStyle("RH2", parent=styles["Heading2"], textColor=INK, fontSize=12, spaceBefore=14, spaceAfter=6)
        body = ParagraphStyle("RBody", parent=styles["Normal"], textColor=INK, fontSize=9.5, leading=14)
        disclaimer_style = ParagraphStyle(
            "RDisclaimer", parent=styles["Normal"], textColor=INK_SOFT, fontSize=8, leading=11,
        )
        risk_style = ParagraphStyle(
            "RRisk", parent=styles["Heading1"], textColor=risk_color, fontSize=22, alignment=TA_CENTER,
        )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        )
        elements = []

        elements.append(Paragraph("RenalAI", title_style))
        elements.append(Paragraph("AI-Powered Kidney Disease Screening &amp; Clinical Decision Support", subtitle_style))

        meta_table = Table(
            [["Report ID", report_id, "Generated", generated_at],
             ["Patient", patient_name or "Not specified", "Report type", "CKD Screening"]],
            colWidths=[28 * mm, 55 * mm, 28 * mm, 55 * mm],
        )
        meta_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("TEXTCOLOR", (0, 0), (0, -1), INK_SOFT),
            ("TEXTCOLOR", (2, 0), (2, -1), INK_SOFT),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, HexColor("#DCE3E8")),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 10))

        # --- Risk summary block ---
        elements.append(Paragraph(f"{risk} RISK", risk_style))
        prob_pct = f"{prediction_result.get('probability_ckd', 0) * 100:.1f}%"
        pred_label = "Pattern consistent with CKD" if prediction_result.get("prediction") == "ckd" else "Pattern not consistent with CKD"
        elements.append(Paragraph(
            f"<para alignment='center'>{pred_label} &nbsp;&middot;&nbsp; Estimated CKD probability: <b>{prob_pct}</b></para>",
            body,
        ))
        elements.append(Spacer(1, 8))

        # --- Clinical parameters table ---
        elements.append(Paragraph("Clinical Parameters", h2))
        param_rows = [["Parameter", "Value"]]
        for key, val in patient_inputs.items():
            if val is None or val == "":
                continue
            label = CLINICAL_LABELS.get(key, key)
            param_rows.append([label, str(val)])
        param_table = Table(param_rows, colWidths=[85 * mm, 85 * mm])
        param_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F2F6F7")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#DCE3E8")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(param_table)
        elements.append(Spacer(1, 8))

        # --- AI Explanation ---
        elements.append(Paragraph("AI Explanation", h2))
        elements.append(Paragraph(prediction_result.get("clinical_explanation", "Not available."), body))
        top_feats = prediction_result.get("top_contributing_features", [])
        if top_feats:
            feat_lines = ", ".join(
                f"{CLINICAL_LABELS.get(f['feature'], f['feature'])} ({f['direction'].replace('_', ' ')})"
                for f in top_feats[:5]
            )
            elements.append(Paragraph(f"<i>Top contributing factors: {feat_lines}</i>", body))
        elements.append(Paragraph(
            f"<i>Explanation method: {prediction_result.get('explanation_method', 'n/a')}</i>",
            disclaimer_style,
        ))
        elements.append(Spacer(1, 8))

        # --- Doctor notes ---
        if doctor_notes:
            elements.append(Paragraph("Doctor Notes", h2))
            elements.append(Paragraph(doctor_notes, body))
            elements.append(Spacer(1, 8))

        # --- Recommendations ---
        elements.append(Paragraph("Recommendations", h2))
        recs = {
            "HIGH": "Prompt nephrology referral is recommended. Confirm with laboratory-verified "
                    "renal function panel and discuss findings with a licensed physician as soon as possible.",
            "MEDIUM": "Consider a follow-up renal function panel and a nephrology consultation to "
                      "clarify risk. Monitor blood pressure, blood glucose, and repeat labs as advised by a clinician.",
            "LOW": "No urgent action indicated by this screening. Routine follow-up and periodic "
                   "screening are still advisable, particularly with any change in symptoms or risk factors.",
        }
        elements.append(Paragraph(recs.get(risk, recs["LOW"]), body))
        elements.append(Spacer(1, 10))

        # --- QR + disclaimer footer ---
        qr_img = _build_qr_image(report_id)
        footer_table = Table(
            [[qr_img, Paragraph(
                "<b>Medical Disclaimer:</b> This report is generated by an AI screening tool "
                "(RenalAI) for clinical decision support only. It is NOT a medical diagnosis and "
                "must not be used as the sole basis for treatment decisions. All results should be "
                "reviewed and confirmed by a licensed physician or nephrologist alongside appropriate "
                "laboratory and clinical evaluation.",
                disclaimer_style,
            )]],
            colWidths=[26 * mm, 144 * mm],
        )
        footer_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        elements.append(footer_table)

        doc.build(elements)
        pdf_bytes = buf.getvalue()

        out_path = REPORTS_DIR / f"{report_id}.pdf"
        out_path.write_bytes(pdf_bytes)

        return pdf_bytes, report_id

    except Exception as e:
        logger.exception("PDF generation failed")
        raise PDFGenerationError(f"Failed to generate PDF report: {e}")
