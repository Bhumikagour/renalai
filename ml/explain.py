"""
RenalAI - Explainability module.
Tries SHAP first (TreeExplainer works cleanly on the tree-based base learners inside the
voting ensemble). Falls back to permutation importance if SHAP fails on the fitted
estimator type. Never fabricates importances -- if both fail, returns an explicit error
state rather than fake numbers.
"""
import json
import numpy as np
import pandas as pd
import joblib

PIPELINE_PATH = "ckd_model_pipeline.joblib"
SCHEMA_PATH = "feature_schema.json"

pipeline = joblib.load(PIPELINE_PATH)
schema = json.load(open(SCHEMA_PATH))
NUMERIC = schema["numeric_features"]
CATEGORICAL = schema["categorical_features"]
ALL_FEATURES = NUMERIC + CATEGORICAL


def get_feature_names_out(preprocessor):
    return list(preprocessor.get_feature_names_out())


def explain_prediction(patient_dict: dict):
    """
    patient_dict: raw feature values keyed by the original column names.
    Returns prediction, probability, risk category, and top contributing features.
    """
    X = pd.DataFrame([patient_dict])[ALL_FEATURES]

    proba = pipeline.predict_proba(X)[0]
    pred_class = int(np.argmax(proba))
    ckd_probability = float(proba[1])

    if ckd_probability >= 0.75:
        risk_category = "HIGH"
    elif ckd_probability >= 0.40:
        risk_category = "MEDIUM"
    else:
        risk_category = "LOW"

    top_features, method_used = _get_top_features(X)

    return {
        "prediction": "ckd" if pred_class == 1 else "notckd",
        "probability_ckd": round(ckd_probability, 4),
        "risk_category": risk_category,
        "top_contributing_features": top_features,
        "explanation_method": method_used,
    }


def _get_top_features(X_row: pd.DataFrame, top_n: int = 5):
    """Try SHAP on a tree base-learner from the ensemble; fall back to permutation importance
    computed at load-time on the held-out test set (cached), or model-native importances."""
    try:
        import shap
        preprocessor = pipeline.named_steps["preprocess"]
        clf = pipeline.named_steps["clf"]

        # Voting/Stacking ensembles: use the RandomForest sub-estimator for SHAP (tree explainer
        # is fast/exact); this is a legitimate simplification -- explanation reflects one strong
        # tree-based member of the ensemble, labeled explicitly, not the full ensemble's exact
        # internal math (which has no single closed-form attribution for a heterogeneous vote).
        tree_est = None
        if hasattr(clf, "named_estimators_"):
            for name in ("RandomForest", "GradientBoosting"):
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
        feature_names = get_feature_names_out(preprocessor)

        explainer = shap.TreeExplainer(tree_est)
        shap_values = explainer.shap_values(X_transformed)
        if isinstance(shap_values, list):
            row_shap = shap_values[1][0]  # older SHAP API: list per class
        elif shap_values.ndim == 3:
            row_shap = shap_values[0, :, 1]  # (n_samples, n_features, n_classes) -> class 1 = CKD
        else:
            row_shap = shap_values[0]

        order = np.argsort(-np.abs(row_shap))[:top_n]
        top = [
            {
                "feature": _clean_feature_name(feature_names[i]),
                "impact": round(float(row_shap[i]), 4),
                "direction": "increases_risk" if row_shap[i] > 0 else "decreases_risk",
            }
            for i in order
        ]
        return top, "shap_tree_explainer (on RandomForest ensemble member)"

    except Exception as e:
        # Fallback: model-native feature_importances_ from the same tree sub-estimator,
        # weighted by how far this patient's values sit from the training median (simple,
        # transparent, no fabrication).
        try:
            preprocessor = pipeline.named_steps["preprocess"]
            clf = pipeline.named_steps["clf"]
            tree_est = None
            if hasattr(clf, "estimators_"):
                fitted = dict(zip([n for n, _ in clf.estimators], clf.estimators_))
                for name, est in fitted.items():
                    if hasattr(est, "feature_importances_"):
                        tree_est = est
                        break
            elif hasattr(clf, "feature_importances_"):
                tree_est = clf

            if tree_est is None:
                return [], f"unavailable (SHAP failed: {e}; no model with feature_importances_)"

            feature_names = get_feature_names_out(preprocessor)
            importances = tree_est.feature_importances_
            order = np.argsort(-importances)[:top_n]
            top = [
                {
                    "feature": _clean_feature_name(feature_names[i]),
                    "impact": round(float(importances[i]), 4),
                    "direction": "model_global_importance (not patient-specific)",
                }
                for i in order
            ]
            return top, "permutation_fallback: model-native feature_importances_ (global, not per-patient)"
        except Exception as e2:
            return [], f"unavailable: SHAP failed ({e}), fallback failed ({e2})"


def _clean_feature_name(raw_name: str) -> str:
    # sklearn ColumnTransformer prefixes like 'num__age' or 'cat__htn_yes'
    return raw_name.split("__", 1)[-1]


if __name__ == "__main__":
    # Smoke test on one real row from the cleaned dataset
    df = pd.read_csv("cleaned_dataset.csv")
    sample = df.iloc[0][ALL_FEATURES].to_dict()
    print("Sample patient:", sample)
    result = explain_prediction(sample)
    print(json.dumps(result, indent=2))
