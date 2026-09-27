from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


class PredictionRequest(BaseModel):
    """Raw clinical inputs. Optional fields allow missing labs -- the trained
    pipeline's imputer handles missing values the same way it did during training."""
    age: Optional[float] = Field(None, ge=0, le=120, description="Age in years")
    bp: Optional[float] = Field(None, ge=30, le=250, description="Blood pressure (mm/Hg)")
    sg: Optional[float] = Field(None, ge=1.000, le=1.030, description="Urine specific gravity")
    al: Optional[float] = Field(None, ge=0, le=5, description="Albumin (0-5)")
    su: Optional[float] = Field(None, ge=0, le=5, description="Sugar (0-5)")
    rbc: Optional[Literal["normal", "abnormal"]] = None
    pc: Optional[Literal["normal", "abnormal"]] = None
    pcc: Optional[Literal["present", "notpresent"]] = None
    ba: Optional[Literal["present", "notpresent"]] = None
    bgr: Optional[float] = Field(None, ge=0, le=800, description="Blood glucose random (mg/dl)")
    bu: Optional[float] = Field(None, ge=0, le=400, description="Blood urea (mg/dl)")
    sc: Optional[float] = Field(None, ge=0, le=80, description="Serum creatinine (mg/dl)")
    sod: Optional[float] = Field(None, ge=0, le=200, description="Sodium (mEq/L)")
    pot: Optional[float] = Field(None, ge=0, le=50, description="Potassium (mEq/L)")
    hemo: Optional[float] = Field(None, ge=0, le=25, description="Hemoglobin (g/dl)")
    pcv: Optional[float] = Field(None, ge=0, le=70, description="Packed cell volume (%)")
    wc: Optional[float] = Field(None, ge=0, le=30000, description="White blood cell count (cells/cumm)")
    rc: Optional[float] = Field(None, ge=0, le=10, description="Red blood cell count (millions/cmm)")
    htn: Optional[Literal["yes", "no"]] = None
    dm: Optional[Literal["yes", "no"]] = None
    cad: Optional[Literal["yes", "no"]] = None
    appet: Optional[Literal["good", "poor"]] = None
    pe: Optional[Literal["yes", "no"]] = None
    ane: Optional[Literal["yes", "no"]] = None

    @field_validator("*", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class TopFeature(BaseModel):
    feature: str
    impact: float
    direction: str


class PredictionResponse(BaseModel):
    prediction: Literal["ckd", "notckd"]
    probability_ckd: float
    risk_category: Literal["LOW", "MEDIUM", "HIGH"]
    top_contributing_features: list[TopFeature]
    explanation_method: str
    clinical_explanation: str
    disclaimer: str = (
        "This is an AI-generated screening estimate for clinical decision support only. "
        "It is NOT a medical diagnosis. Consult a licensed nephrologist for interpretation "
        "and confirmatory testing."
    )
