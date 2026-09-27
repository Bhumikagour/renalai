"""
Explainability service used by the /predictions API.
Loads the trained pipeline ONCE at import time and reuses it for every request
(per spec: 'The API must load the trained model once and reuse it').
"""
import json
import logging
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
import joblib

logger = logging.getLogger("renalai.explain")

ARTIFACT_DIR = Path(__file__).resolve().parent.parent.parent / "model_artifacts"
PIPELINE_PATH = ARTIFACT_DIR / "ckd_model_pipeline.joblib"
SCHEMA_PATH = ARTIFACT_DIR / "feature_schema.json"

_pipeline = None
_schema = None
_load_error = None

try:
    _pipeline = joblib.load(PIPELINE_PATH)
    _schema = json.load(open(SCHEMA_PATH))
    logger.info("CKD model pipeline loaded successfully from %s", PIPELINE_PATH)
except Exception as e:
    _load_error = str(e)
    logger.error("FAILED to load CKD model pipeline: %s", e)


def model_is_ready() -> bool:
    return _pipeline is not None and _schema is not None


def get_load_error() -> str:
    return _load_error or "unknown error"


def get_feature_schema() -> dict:
    if _schema is None:
        raise RuntimeError("Feature schema not loaded")
    return _schema


def _clean_feature_name(raw_name: str) -> str:
    return raw_name.split("__", 1)[-1]


def _base_feature_of(onehot_col_name: str, categorical_cols: list) -> str:
    """Map a one-hot column like 'htn_yes' back to its base categorical field 'htn'."""
    for cat in categorical_cols:
        if onehot_col_name == cat or onehot_col_name.startswith(cat + "_"):
            return cat
    return onehot_col_name


def explain_prediction(patient_dict: dict, top_n: int = 5) -> dict:
    if not model_is_ready():
        raise RuntimeError(f"Model not loaded: {_load_error}")

    numeric = _schema["numeric_features"]
    categorical = _schema["categorical_features"]
    all_features = numeric + categorical

    missing_cols = [c for c in all_features if c not in patient_dict]
    if missing_cols:
        raise ValueError(f"Missing required fields: {missing_cols}")

    X = pd.DataFrame([patient_dict])[all_features]

    proba = _pipeline.predict_proba(X)[0]
    pred_class = int(np.argmax(proba))
    ckd_probability = float(proba[1])

    if ckd_probability >= 0.75:
        risk_category = "HIGH"
    elif ckd_probability >= 0.40:
        risk_category = "MEDIUM"
    else:
        risk_category = "LOW"

    top_features, method_used = _get_top_features(X, categorical, top_n)

    return {
        "prediction": "ckd" if pred_class == 1 else "notckd",
        "probability_ckd": round(ckd_probability, 4),
        "risk_category": risk_category,
        "top_contributing_features": top_features,
        "explanation_method": method_used,
        "clinical_explanation": _build_clinical_explanation(risk_category, top_features),
    }


def _get_top_features(X_row: pd.DataFrame, categorical_cols: list, top_n: int):
    try:
        import shap
        preprocessor = _pipeline.named_steps["preprocess"]
        clf = _pipeline.named_steps["clf"]

        tree_est = None
        if hasattr(clf, "named_estimators_"):
            for name in ("RandomForest", "GradientBoosting", "ExtraTrees"):
                if name in clf.named_estimators_:
                    tree_est = clf.named_estimators_[name]
                    break
        elif hasattr(clf, "feature_importances_"):
            tree_est = clf

        if tree_est is None:
            raise ValueError("No tree-based estimator available for SHAP TreeExplainer")

        X_transformed = preprocessor.transform(X_row)
        if hasattr(X_transformed, "toarray"):
            X_transformed = X_transformed.toarray()
        feature_names = [_clean_feature_name(n) for n in preprocessor.get_feature_names_out()]

        explainer = shap.TreeExplainer(tree_est)
        shap_values = explainer.shap_values(X_transformed)
        if isinstance(shap_values, list):
            row_shap = shap_values[1][0]
        elif shap_values.ndim == 3:
            row_shap = shap_values[0, :, 1]
        else:
            row_shap = shap_values[0]

        # Aggregate one-hot columns back to their original categorical field so
        # 'htn_yes' + 'htn_no' don't both show up as separate top features.
        agg = defaultdict(float)
        for name, val in zip(feature_names, row_shap):
            base = _base_feature_of(name, categorical_cols)
            agg[base] += float(val)

        ranked = sorted(agg.items(), key=lambda kv: -abs(kv[1]))[:top_n]
        top = [
            {
                "feature": feat,
                "impact": round(val, 4),
                "direction": "increases_risk" if val > 0 else "decreases_risk",
            }
            for feat, val in ranked
        ]
        return top, "shap_tree_explainer"

    except Exception as e:
        logger.warning("SHAP explanation failed, falling back to feature_importances_: %s", e)
        try:
            preprocessor = _pipeline.named_steps["preprocess"]
            clf = _pipeline.named_steps["clf"]
            tree_est = None
            if hasattr(clf, "named_estimators_"):
                for name, est in clf.named_estimators_.items():
                    if hasattr(est, "feature_importances_"):
                        tree_est = est
                        break
            elif hasattr(clf, "feature_importances_"):
                tree_est = clf

            if tree_est is None:
                return [], f"unavailable (SHAP failed: {e}; no feature_importances_ available)"

            feature_names = [_clean_feature_name(n) for n in preprocessor.get_feature_names_out()]
            importances = tree_est.feature_importances_
            agg = defaultdict(float)
            for name, val in zip(feature_names, importances):
                base = _base_feature_of(name, categorical_cols)
                agg[base] += float(val)
            ranked = sorted(agg.items(), key=lambda kv: -kv[1])[:top_n]
            top = [
                {"feature": feat, "impact": round(val, 4), "direction": "global_importance"}
                for feat, val in ranked
            ]
            return top, "feature_importance_fallback (global, not patient-specific; SHAP unavailable)"
        except Exception as e2:
            return [], f"unavailable: SHAP failed ({e}), fallback failed ({e2})"


_CLINICAL_LABELS = {
    "sc": "serum creatinine", "bu": "blood urea", "hemo": "hemoglobin",
    "pcv": "packed cell volume", "al": "albumin in urine", "sg": "urine specific gravity",
    "htn": "hypertension", "dm": "diabetes mellitus", "rc": "red blood cell count",
    "sod": "sodium", "pot": "potassium", "bgr": "blood glucose", "bp": "blood pressure",
    "age": "age", "wc": "white blood cell count", "su": "sugar in urine",
    "rbc": "red blood cells (urine)", "pc": "pus cells", "pcc": "pus cell clumps",
    "ba": "bacteria", "cad": "coronary artery disease", "appet": "appetite",
    "pe": "pedal edema", "ane": "anemia",
}


def _build_clinical_explanation(risk_category: str, top_features: list) -> str:
    if not top_features:
        return (
            "This is an AI-generated screening estimate, not a diagnosis. "
            "Feature-level explanation is unavailable for this prediction."
        )
    labels = [_CLINICAL_LABELS.get(f["feature"], f["feature"]) for f in top_features[:3]]
    joined = ", ".join(labels)
    return (
        f"This {risk_category.lower()}-risk screening estimate was most influenced by: {joined}. "
        "This is an AI-generated screening signal to support clinical review, not a diagnosis. "
        "Always confirm with a licensed nephrologist and appropriate lab/imaging workup."
    )
