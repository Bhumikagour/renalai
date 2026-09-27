# RenalAI — CKD Screening MVP+

An AI-assisted chronic kidney disease (CKD) screening platform: a trained ML
pipeline, a FastAPI backend serving explainable predictions plus OCR, PDF
reports, an AI chatbot, a prototype imaging pipeline, and nephrologist
location search — and a Next.js frontend tying it together. See "Not
included" at the bottom for what's still missing from the original full spec
(auth, database, role-based dashboards, etc).

## 1. Project structure

```
renalai/
├── ml/                          # training pipeline (run once to produce artifacts)
│   ├── raw_dataset.csv          # the uploaded ESRD/CKD dataset (400 rows)
│   ├── clean_data.py            # cleaning: whitespace, dirty target, numeric coercion
│   ├── cleaned_dataset.csv      # output of clean_data.py
│   ├── feature_schema.json      # single source of truth for feature names/types
│   ├── train_models.py          # compares 9 models + voting/stacking ensembles
│   ├── model_comparison_results.csv
│   ├── model_metadata.json      # exact metrics for the selected model
│   ├── ckd_model_pipeline.joblib # the trained sklearn Pipeline (preprocessing + model)
│   └── explain.py               # standalone SHAP/fallback explainability smoke test
│
├── backend/                     # FastAPI service
│   ├── app/
│   │   ├── main.py              # app entrypoint, CORS, /health, all routers
│   │   ├── routers/
│   │   │   ├── predictions.py   # POST /predictions, GET /predictions/schema
│   │   │   ├── ocr.py           # POST /ocr/scan
│   │   │   ├── reports.py       # POST /reports/generate (PDF)
│   │   │   ├── chat.py          # POST /chat, GET /chat/status
│   │   │   ├── imaging.py       # POST /imaging/upload, GET /imaging/history
│   │   │   └── location.py      # GET /location/nearby, GET /location/status
│   │   ├── schemas/prediction.py
│   │   └── core/
│   │       ├── explain.py       # loads model ONCE, SHAP + fallback logic
│   │       ├── ocr_service.py   # tesseract OCR + regex lab-value extraction
│   │       ├── pdf_service.py   # reportlab PDF report generation + QR code
│   │       ├── chat_service.py  # Anthropic-API-backed chatbot, env-configured
│   │       ├── imaging_service.py  # upload/validate/preprocess pipeline (prototype)
│   │       └── location_service.py # Google Places-backed search, env-configured
│   ├── model_artifacts/         # copy of the trained pipeline + schema + metadata
│   ├── uploads/{ocr,imaging}/   # uploaded documents/images are saved here
│   ├── reports/                 # generated PDF reports are saved here
│   └── requirements.txt
│
└── frontend/                    # Next.js (TypeScript, Tailwind) app
    ├── app/
    │   ├── page.tsx              # tabbed UI: Screening / Scan document / Imaging / Find specialists
    │   ├── components/
    │   │   ├── KidneyPulse.tsx   # risk-reactive kidney visual
    │   │   ├── OCRScanner.tsx    # upload + review-before-apply OCR flow
    │   │   ├── ImagingUpload.tsx # CT/MRI/USG prototype upload
    │   │   ├── NearbySpecialists.tsx  # geolocation + nearby search
    │   │   └── ChatWidget.tsx    # floating Kidney Health Assistant
    │   ├── lib/api.ts            # typed fetch clients for every endpoint
    │   └── globals.css           # design tokens
    └── package.json
```

## 2. Run instructions

### System dependency (OCR)
Tesseract OCR must be installed on the host (not just the Python wrapper):
```bash
sudo apt-get install -y tesseract-ocr poppler-utils
```

### Train the model (optional — trained artifacts are already included)
```bash
cd ml
pip install -r ../backend/requirements.txt
python3 clean_data.py
python3 train_models.py
cp ckd_model_pipeline.joblib feature_schema.json model_metadata.json ../backend/model_artifacts/
```

### Backend
```bash
cd backend
pip install -r requirements.txt
# optional: export ANTHROPIC_API_KEY=...      (enables the chatbot)
# optional: export GOOGLE_MAPS_API_KEY=...    (enables nearby specialist search)
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# Docs at http://localhost:8000/docs
# Health check at http://localhost:8000/health (also reports optional-service status)
```

### Frontend
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
# open http://localhost:3000
```

## 3. Environment variables

| Variable | Where | Required | Purpose |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | frontend `.env.local` | Yes | Base URL of the FastAPI backend |
| `ANTHROPIC_API_KEY` | backend environment | No | Enables the Kidney Health AI Assistant chatbot |
| `RENALAI_CHAT_MODEL` | backend environment | No | Overrides the chat model (default `claude-sonnet-4-6`) |
| `GOOGLE_MAPS_API_KEY` | backend environment | No | Enables nearby nephrologist/hospital search |

Without the two optional keys, the app runs fully — the chatbot and location
search each return an explicit "not configured" state (never a crash, never a
fake answer) and core CKD prediction, OCR, PDF reports, and the imaging
pipeline are entirely unaffected.

## 4. ML results (actual, not invented)

Dataset: 400 rows, public UCI/Kaggle CKD benchmark, cleaned as described in
`ml/clean_data.py`. Split: 80/20 stratified, `random_state=42`. Selection
metric: cross-validated CKD recall (sensitivity) first, ROC-AUC as tie-break —
not raw accuracy, per the medical-safety requirement to minimize missed CKD cases.

**Selected model: Voting Ensemble (RandomForest + GradientBoosting + LogisticRegression)**

| Metric | 5-fold CV (validation) | Held-out test set |
|---|---|---|
| Accuracy | 99.06% | 100% |
| Recall (CKD sensitivity) | 100% | 100% |
| Precision | 98.56% | 100% |
| Specificity | — | 100% |
| F1 | 99.27% | 100% |
| ROC-AUC | 100% | 100% |
| Train–val accuracy gap | 0.94 pts | — |

Full comparison across all 11 candidates (9 base models + 2 ensembles) is in
`ml/model_comparison_results.csv`.

**On the 100% test score:** investigated, not assumed safe. `id` dropped
before training; imputation/scaling fit only inside the Pipeline on training
folds (no leakage into test); class means for the top predictive features
(serum creatinine 4.4 vs 0.87 mg/dl, hemoglobin 10.6 vs 15.2 g/dl, albuminuria
present only in CKD cases) match known clinical CKD markers. Near-perfect
scores on this exact 400-row UCI benchmark are a documented property of the
dataset — not evidence by itself of a code error, and not a guarantee this
generalizes to a new hospital's patient population.

## 5. New features in this update (all tested live, not just written)

- **OCR document scanner** (`POST /ocr/scan`): Tesseract-based extraction from
  PNG/JPG/PDF lab reports, with regex lab-value parsing. Every extracted value
  carries a confidence level and, when a value falls outside a plausible
  physiological range, an explicit flag (this genuinely caught a real OCR
  error in testing — a dropped decimal point turning "2.1" into "21" for
  serum creatinine). The frontend never auto-applies OCR output; the user
  must review and click "Apply reviewed values to form."
- **PDF clinical reports** (`POST /reports/generate`): branded report with
  patient info, prediction, probability, risk level, full clinical parameter
  table, AI explanation with top contributing factors, doctor notes, a QR
  code, timestamp, report ID, and medical disclaimer. Independent of the
  prediction endpoint — a PDF failure never breaks a prediction and vice versa.
- **Kidney Health AI Assistant** (`POST /chat`, floating widget in the UI):
  Anthropic-API-backed, system-prompted to never present itself as a doctor
  and to always include safety framing. Environment-configured
  (`ANTHROPIC_API_KEY`); gracefully reports an "unavailable" state with no
  key configured, verified live in this build.
- **Medical imaging pipeline** (`POST /imaging/upload`): real upload
  validation, decode, resize, and normalization for CT/MRI/USG images. No
  trained imaging model exists in this project (the CKD model is
  structured-data-only and cannot analyze images) — every response is
  explicitly labeled `"Prototype Imaging Analysis Pipeline"` with no
  fabricated diagnosis, exactly per spec.
- **Nearby specialist search** (`GET /location/nearby`, browser geolocation
  in the UI): Google Places-backed search across nephrologists, kidney
  hospitals, dialysis centers, and emergency hospitals. Handles permission
  denial, missing browser support, and a missing API key each with a distinct,
  honest UI state — verified live with geolocation granted in this build.

## 5b. This update: patient dashboard, voice assistant, Grad-CAM

- **Patient dashboard** (new default tab, `frontend/app/components/PatientDashboard.tsx`):
  a single patient-facing screen with a risk snapshot (current session result,
  or the last one saved on this device), a small trend view of the last 6
  screenings, imaging activity summary, and quick-action tiles to the other
  tabs. There is still no backend database (see section 8), so history is
  read from `localStorage` via `frontend/app/lib/history.ts` — an explicit
  MVP shim, not a clinical record store. It is written to whenever a
  screening or imaging upload succeeds.
- **Voice assistant** (`frontend/app/components/ChatWidget.tsx`): the existing
  chat widget now supports speech input (Web Speech API `SpeechRecognition` —
  Chrome/Edge; feature-detected, the mic button is simply hidden where
  unsupported) and optional spoken replies (`speechSynthesis`, toggled per
  session, plus a per-message replay button). No new backend surface — it
  talks to the same `POST /chat` endpoint.
- **Grad-CAM** (`backend/app/core/gradcam_service.py`, wired into
  `POST /imaging/upload`): a real Grad-CAM implementation (forward/backward
  hooks on the last conv block, gradient-weighted activation map, ReLU,
  upsample, overlay) run against an ImageNet-pretrained ResNet-18, since — as
  documented in section 5 — no trained kidney-imaging model exists in this
  project. The algorithm is genuine; what it visualizes is what a
  general-purpose vision network attends to in the pixels, not a kidney
  finding. The response is explicit about this (`gradcam.note`) and the
  frontend surfaces that same wording next to the heatmap. Runs only for
  PNG/JPEG uploads that preprocess successfully; DICOM and failed
  preprocessing get a clear "unavailable" state instead of a silent skip.
  Requires `torch`/`torchvision` (added to `backend/requirements.txt`) — not
  importable or exercised in the development sandbox (no network access to
  fetch the pretrained weights or the packages themselves), so this was
  verified by code review and manual tracing, not a live run. Run
  `pip install -r backend/requirements.txt` and re-check `GET /health` →
  `optional_services.gradcam` before relying on it.

## 6. External dependencies

- **AI chatbot**: requires `ANTHROPIC_API_KEY`. Not tested against a live key
  in this build (none was available in the development sandbox) — the
  request/response wiring follows the standard Anthropic Messages API and the
  graceful-unavailable path was verified instead.
- **Nearby nephrologists / maps**: requires `GOOGLE_MAPS_API_KEY`. Same
  caveat — graceful-unavailable path verified; live Places API calls were not
  reachable from the development sandbox's network.
- **Medical imaging (CT/MRI/USG)**: requires a separately trained imaging
  model and imaging dataset, neither of which exists in this project by
  design — see the scientific note in section 5.
- **OCR**: requires the `tesseract-ocr` system package (see run instructions).

## 7. Known limitations

- **Dataset size**: 400 rows total, 320 used for training — small for a
  clinical model; generalization to a real hospital population is unverified.
- **Single-source data**, no independent validation cohort, **no clinical
  validation** by a nephrologist, and **no regulatory clearance** — must not
  be used for real patient care decisions.
- **Explainability caveat**: SHAP attribution runs on one tree-based member
  of the voting ensemble (RandomForest), not a closed-form attribution of the
  full heterogeneous ensemble vote — disclosed simplification, not exact.
- **OCR accuracy**: regex-based extraction over Tesseract text is inherently
  imperfect on real-world scans (skew, poor lighting, handwriting). The
  range-based flagging catches some but not all misreads — human review is
  mandatory, not optional, which is why the UI enforces a review step.
- **No persistence layer**: predictions, OCR scans, and imaging results are
  not saved to a database — imaging history is in-memory only and clears on
  backend restart.
- **No authentication**: the API is fully open — do not deploy this publicly
  as-is.
- **Chatbot and location search are architecturally complete but functionally
  unverified against live external APIs** in this build, for the reasons in
  section 6 — test with real keys before relying on them.

## 8. What's NOT built yet (from the original full spec)

Patient/Doctor/Nurse/Hospital role-based dashboards, database models (User,
PatientRecord, VitalRecord, etc.), JWT auth, role-based authorization, audit
logging, appointments, voice assistant (browser speech recognition/TTS), and
Grad-CAM visualization (the imaging interface has a `gradcam_available` flag
ready for this, but no implementation since there's no trained imaging model
to visualize). Happy to continue with any of these next.
