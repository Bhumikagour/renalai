# RenalAI backend — FastAPI + scikit-learn + SHAP + Tesseract OCR
#
# Docker rather than Render's native Python runtime because the OCR endpoints
# need the `tesseract` binary, and Render's Python builds run without root, so
# `apt-get install tesseract-ocr` in a buildCommand fails.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMBA_NUM_THREADS=1

# tesseract-ocr + eng  -> /ocr endpoints
# libgomp1             -> OpenMP runtime scikit-learn links against
# libglib2.0-0, libgl1 -> shared libs PyMuPDF needs
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libgomp1 \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app/ ./app/
COPY model_artifacts/ ./model_artifacts/

# Fail the BUILD, not the deploy, if the model artifact can't be unpickled.
RUN python -c "from app.core import explain; assert explain.model_is_ready(), explain.get_load_error(); print('model artifact loads OK')"

EXPOSE 8000

# One worker: model + SHAP sit near 350MB RSS against a 512MB free-tier limit.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
