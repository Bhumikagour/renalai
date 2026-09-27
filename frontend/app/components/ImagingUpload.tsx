"use client";

import { useState } from "react";
import { uploadImagingScan, ApiError, ImagingResult } from "../lib/api";
import { addImagingRecord } from "../lib/history";

const MODALITIES = [
  { key: "ct", label: "CT Scan" },
  { key: "mri", label: "MRI" },
  { key: "usg", label: "Ultrasound (USG)" },
];

export default function ImagingUpload() {
  const [modality, setModality] = useState("ct");
  const [result, setResult] = useState<ImagingResult | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPreview(URL.createObjectURL(file));
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await uploadImagingScan(file, modality);
      setResult(res);
      addImagingRecord(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Imaging upload failed.");
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  }

  return (
    <div className="bg-[var(--surface)] border border-[var(--line)] rounded-xl p-5">
      <h3 className="font-[family-name:var(--font-display)] font-semibold text-sm mb-1">
        Medical imaging (CT / MRI / USG)
      </h3>
      <div className="text-xs bg-[var(--risk-medium)]/10 border border-[var(--risk-medium)]/30 text-[var(--ink)] rounded-lg p-3 mb-3 leading-relaxed">
        <strong>Prototype pipeline.</strong> No trained kidney imaging model exists in this
        project. The CKD prediction model uses lab values only and cannot analyze images.
        This demonstrates the upload → validate → preprocess → inference → Grad-CAM
        architecture end-to-end. The Grad-CAM heatmap below is computed for real, but
        against a general-purpose ImageNet backbone — it shows what a generic vision
        network attends to, not a kidney finding, and it will never show a fabricated
        diagnosis.
      </div>

      <div className="flex gap-2 mb-3">
        {MODALITIES.map((m) => (
          <button
            key={m.key}
            type="button"
            onClick={() => setModality(m.key)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              modality === m.key
                ? "bg-[var(--primary)] text-white border-[var(--primary)]"
                : "border-[var(--line)] hover:border-[var(--primary)]"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <label className="inline-flex items-center gap-2 text-xs font-medium px-3 py-2 rounded-lg border border-[var(--line)] cursor-pointer hover:border-[var(--primary)] transition-colors">
        {loading ? "Uploading…" : "Choose image"}
        <input type="file" accept=".png,.jpg,.jpeg" className="hidden" onChange={handleFile} disabled={loading} />
      </label>

      {error && (
        <div className="mt-3 text-sm text-[var(--risk-high)] bg-[var(--risk-high)]/8 border border-[var(--risk-high)]/30 rounded-lg p-3">
          {error}
        </div>
      )}

      {(preview || result) && (
        <div className="mt-4 grid sm:grid-cols-[120px_1fr] gap-4 items-start">
          {preview && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={preview} alt="Uploaded scan preview" className="w-full sm:w-[120px] rounded-lg border border-[var(--line)] object-cover" />
          )}
          {result && (
            <div className="text-sm">
              <div className="font-medium mb-1">{result.label}</div>
              <div className="text-xs text-[var(--ink-soft)] mb-2">
                Modality: {result.modality.toUpperCase()} · Preprocessing:{" "}
                {result.preprocessing_ok ? "completed" : "failed"}
              </div>
              <p className="text-xs text-[var(--ink-soft)] leading-relaxed">{result.result.message}</p>
            </div>
          )}
        </div>
      )}

      {result?.gradcam && (
        <div className="mt-5 pt-4 border-t border-[var(--line)]">
          <h4 className="font-[family-name:var(--font-display)] font-semibold text-sm mb-1">
            Grad-CAM visual explainability
          </h4>

          {result.gradcam.available && result.gradcam.overlay_base64 ? (
            <div className="grid sm:grid-cols-[160px_1fr] gap-4 items-start mt-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`data:image/png;base64,${result.gradcam.overlay_base64}`}
                alt="Grad-CAM saliency heatmap overlay"
                className="w-full sm:w-[160px] rounded-lg border border-[var(--line)] object-cover"
              />
              <div className="text-xs text-[var(--ink-soft)] leading-relaxed space-y-2">
                <p>{result.gradcam.note}</p>
                {result.gradcam.backbone && (
                  <p className="font-[family-name:var(--font-mono)] text-[11px]">
                    Backbone: {result.gradcam.backbone}
                    {typeof result.gradcam.backbone_confidence === "number" && (
                      <> · activation confidence {(result.gradcam.backbone_confidence * 100).toFixed(1)}%</>
                    )}
                  </p>
                )}
              </div>
            </div>
          ) : (
            <p className="text-xs text-[var(--ink-soft)] leading-relaxed mt-2">{result.gradcam?.note}</p>
          )}
        </div>
      )}
    </div>
  );
}
