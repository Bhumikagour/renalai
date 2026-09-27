"""
RenalAI - Data Cleaning Pipeline for the ESRD/CKD dataset.

Handles the real issues found on inspection:
- Target column has 3 raw values due to a trailing-tab variant of 'ckd'
- pcv / wc / rc are numeric columns stored as text due to stray '\t?' tokens
- dm / cad have whitespace/tab-prefixed duplicate categories
- id column is a pure row index -> excluded from modeling (leakage risk)
"""
import pandas as pd
import numpy as np
import json

RAW_PATH = "raw_dataset.csv"
OUT_PATH = "cleaned_dataset.csv"
SCHEMA_PATH = "feature_schema.json"

NUMERIC_COLS = [
    "age", "bp", "sg", "al", "su", "bgr", "bu", "sc", "sod", "pot",
    "hemo", "pcv", "wc", "rc",
]
CATEGORICAL_COLS = [
    "rbc", "pc", "pcc", "ba", "htn", "dm", "cad", "appet", "pe", "ane",
]
TARGET_COL = "classification"
ID_COL = "id"


def clean_string(x):
    if pd.isna(x):
        return np.nan
    return str(x).strip().strip("\t").strip()


def main():
    df = pd.read_csv(RAW_PATH)
    print(f"Loaded raw dataset: {df.shape}")

    # Normalize column names (strip whitespace / lowercase already matches, but be safe)
    df.columns = [c.strip().lower() for c in df.columns]

    # --- Clean target column first ---
    df[TARGET_COL] = df[TARGET_COL].apply(clean_string)
    print("Raw target values:", df[TARGET_COL].unique())
    df[TARGET_COL] = df[TARGET_COL].replace({"ckd": "ckd", "notckd": "notckd"})
    # Anything not exactly one of the two canonical values is a data issue -> inspect
    bad_targets = df[~df[TARGET_COL].isin(["ckd", "notckd"])]
    if len(bad_targets):
        print(f"WARNING: {len(bad_targets)} rows with unrecognized target values, dropping:")
        print(bad_targets[TARGET_COL].unique())
        df = df[df[TARGET_COL].isin(["ckd", "notckd"])]
    print("Cleaned target distribution:\n", df[TARGET_COL].value_counts())

    # --- Clean categorical columns: strip whitespace/tabs, lowercase ---
    for col in CATEGORICAL_COLS:
        df[col] = df[col].apply(clean_string).str.lower()
        # collapse any stray non-standard tokens to NaN (defensive)
        valid_vals = {
            "rbc": {"normal", "abnormal"},
            "pc": {"normal", "abnormal"},
            "pcc": {"present", "notpresent"},
            "ba": {"present", "notpresent"},
            "htn": {"yes", "no"},
            "dm": {"yes", "no"},
            "cad": {"yes", "no"},
            "appet": {"good", "poor"},
            "pe": {"yes", "no"},
            "ane": {"yes", "no"},
        }[col]
        invalid_mask = df[col].notna() & ~df[col].isin(valid_vals)
        if invalid_mask.any():
            print(f"  {col}: {invalid_mask.sum()} unexpected values -> set to NaN: "
                  f"{df.loc[invalid_mask, col].unique()}")
            df.loc[invalid_mask, col] = np.nan

    # --- Clean numeric columns: strip whitespace/tabs, coerce, invalid -> NaN ---
    for col in NUMERIC_COLS:
        df[col] = df[col].apply(clean_string)
        before_na = df[col].isna().sum()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        after_na = df[col].isna().sum()
        coerced = after_na - before_na
        if coerced > 0:
            print(f"  {col}: {coerced} non-numeric tokens coerced to NaN")

    # --- Drop identifier column (leakage / no signal) ---
    if ID_COL in df.columns:
        df = df.drop(columns=[ID_COL])
        print(f"Dropped identifier column: {ID_COL}")

    # --- Sanity range checks (flag, don't silently drop rows) ---
    range_checks = {
        "age": (0, 120), "bp": (30, 200), "sg": (1.000, 1.030),
        "hemo": (2, 20), "pcv": (5, 60),
    }
    for col, (lo, hi) in range_checks.items():
        out_of_range = df[(df[col].notna()) & ((df[col] < lo) | (df[col] > hi))]
        if len(out_of_range):
            print(f"  {col}: {len(out_of_range)} out-of-expected-range values found "
                  f"(kept, flagged for review): {out_of_range[col].tolist()}")

    # Save cleaned dataset (still has NaNs -- imputation happens inside the sklearn Pipeline,
    # not here, so train/test splits don't leak imputation statistics)
    df.to_csv(OUT_PATH, index=False)
    print(f"\nSaved cleaned dataset: {df.shape} -> {OUT_PATH}")

    # Save feature schema as the single source of truth for backend + frontend
    schema = {
        "target_column": TARGET_COL,
        "target_classes": {"positive_class": "ckd", "negative_class": "notckd"},
        "numeric_features": NUMERIC_COLS,
        "categorical_features": CATEGORICAL_COLS,
        "categorical_allowed_values": {
            "rbc": ["normal", "abnormal"],
            "pc": ["normal", "abnormal"],
            "pcc": ["present", "notpresent"],
            "ba": ["present", "notpresent"],
            "htn": ["yes", "no"],
            "dm": ["yes", "no"],
            "cad": ["yes", "no"],
            "appet": ["good", "poor"],
            "pe": ["yes", "no"],
            "ane": ["yes", "no"],
        },
        "dropped_columns": [ID_COL],
        "n_rows_after_cleaning": int(len(df)),
        "missing_value_counts": {c: int(df[c].isna().sum()) for c in df.columns},
    }
    with open(SCHEMA_PATH, "w") as f:
        json.dump(schema, f, indent=2)
    print(f"Saved feature schema -> {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
