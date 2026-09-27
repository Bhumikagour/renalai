"use client";

import { useState } from "react";
import { scanDocument, ApiError, OCRResult } from "../lib/api";

export default function OCRScanner({
  onApply,
}: {
  onApply: (values: Record<string, string>) => void;
}) {
  const [result, setResult] = useState<OCRResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState(false);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setApplied(false);
    try {
      const res = await scanDocument(file);
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "OCR scan failed.");
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  }

  function applyToForm() {
    if (!result) return;
    const values: Record<string, string> = {};
    for (const [key, field] of Object.entries(result.extracted_fields)) {
      values[key] = String(field.value);
    }
    onApply(values);
    setApplied(true);
  }

  return (
    <div className="bg-[var(--surface)] border border-[var(--line)] rounded-xl p-5">
      <div className="flex items-center justify-between mb-1">
        <h3 className="font-[family-name:var(--font-display)] font-semibold text-sm">
          Scan a lab report
        </h3>
        <span className="text-xs text-[var(--ink-soft)]">PNG · JPG · PDF</span>
      </div>
      <p className="text-xs text-[var(--ink-soft)] mb-3">
        Upload a photo or PDF of a lab report. Extracted values always require your review
        before they're used — OCR is never trusted automatically.
      </p>

      <label className="inline-flex items-center gap-2 text-xs font-medium px-3 py-2 rounded-lg border border-[var(--line)] cursor-pointer hover:border-[var(--primary)] transition-colors">
        {loading ? "Scanning…" : "Choose file"}
        <input
          type="file"
          accept=".png,.jpg,.jpeg,.pdf"
          className="hidden"
          onChange={handleFile}
          disabled={loading}
        />
      </label>

      {error && (
        <div className="mt-3 text-sm text-[var(--risk-high)] bg-[var(--risk-high)]/8 border border-[var(--risk-high)]/30 rounded-lg p-3">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-4">
          {result.warning && (
            <p className="text-xs text-[var(--risk-medium)] mb-3">{result.warning}</p>
          )}
          {Object.keys(result.extracted_fields).length > 0 && (
            <>
              <div className="text-xs text-[var(--ink-soft)] mb-2">
                Found {result.fields_found} of {result.fields_total} fields — review before applying:
              </div>
              <ul className="space-y-1.5 mb-3 max-h-56 overflow-y-auto pr-1">
                {Object.entries(result.extracted_fields).map(([key, field]) => (
                  <li key={key} className="text-sm">
                    <div className="flex items-center justify-between">
                      <span className="capitalize font-medium">{key}</span>
                      <span className="font-[family-name:var(--font-mono)]">{field.value}</span>
                    </div>
                    {field.flag && (
                      <div className="text-xs text-[var(--risk-high)] mt-0.5">{field.flag}</div>
                    )}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                onClick={applyToForm}
                className="w-full text-sm font-medium px-4 py-2 rounded-lg bg-[var(--primary)] text-white hover:bg-[var(--primary-dark)] transition-colors"
              >
                {applied ? "Applied to form ✓" : "Apply reviewed values to form"}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
