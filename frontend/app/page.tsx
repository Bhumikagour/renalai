"use client";

import { useState } from "react";
import KidneyPulse from "./components/KidneyPulse";
import OCRScanner from "./components/OCRScanner";
import ImagingUpload from "./components/ImagingUpload";
import NearbySpecialists from "./components/NearbySpecialists";
import ChatWidget from "./components/ChatWidget";
import PatientDashboard from "./components/PatientDashboard";
import { predictCKD, downloadReport, ApiError, PredictionResult, PredictionPayload } from "./lib/api";
import { addScreeningRecord } from "./lib/history";

type FieldDef = {
  key: string;
  label: string;
  unit?: string;
  type: "number" | "select";
  options?: string[];
  placeholder?: string;
  step?: string;
};

const BASIC: FieldDef[] = [
  { key: "age", label: "Age", unit: "years", type: "number", placeholder: "e.g. 52" },
  { key: "bp", label: "Blood pressure", unit: "mm/Hg", type: "number", placeholder: "e.g. 80" },
];

const URINE: FieldDef[] = [
  { key: "sg", label: "Specific gravity", type: "number", step: "0.001", placeholder: "e.g. 1.020" },
  { key: "al", label: "Albumin", unit: "0–5", type: "number", placeholder: "e.g. 1" },
  { key: "su", label: "Sugar", unit: "0–5", type: "number", placeholder: "e.g. 0" },
  { key: "rbc", label: "Red blood cells", type: "select", options: ["normal", "abnormal"] },
  { key: "pc", label: "Pus cells", type: "select", options: ["normal", "abnormal"] },
  { key: "pcc", label: "Pus cell clumps", type: "select", options: ["present", "notpresent"] },
  { key: "ba", label: "Bacteria", type: "select", options: ["present", "notpresent"] },
];

const BLOOD: FieldDef[] = [
  { key: "bgr", label: "Blood glucose (random)", unit: "mg/dl", type: "number", placeholder: "e.g. 121" },
  { key: "bu", label: "Blood urea", unit: "mg/dl", type: "number", placeholder: "e.g. 36" },
  { key: "sc", label: "Serum creatinine", unit: "mg/dl", type: "number", step: "0.1", placeholder: "e.g. 1.2" },
  { key: "sod", label: "Sodium", unit: "mEq/L", type: "number", placeholder: "e.g. 138" },
  { key: "pot", label: "Potassium", unit: "mEq/L", type: "number", step: "0.1", placeholder: "e.g. 4.2" },
  { key: "hemo", label: "Hemoglobin", unit: "g/dl", type: "number", step: "0.1", placeholder: "e.g. 15.4" },
  { key: "pcv", label: "Packed cell volume", unit: "%", type: "number", placeholder: "e.g. 44" },
  { key: "wc", label: "White blood cell count", unit: "cells/cumm", type: "number", placeholder: "e.g. 7800" },
  { key: "rc", label: "Red blood cell count", unit: "millions/cmm", type: "number", step: "0.1", placeholder: "e.g. 5.2" },
];

const HISTORY: FieldDef[] = [
  { key: "htn", label: "Hypertension", type: "select", options: ["yes", "no"] },
  { key: "dm", label: "Diabetes mellitus", type: "select", options: ["yes", "no"] },
  { key: "cad", label: "Coronary artery disease", type: "select", options: ["yes", "no"] },
  { key: "appet", label: "Appetite", type: "select", options: ["good", "poor"] },
  { key: "pe", label: "Pedal edema", type: "select", options: ["yes", "no"] },
  { key: "ane", label: "Anemia", type: "select", options: ["yes", "no"] },
];

const PANELS: { title: string; note: string; fields: FieldDef[] }[] = [
  { title: "Basic", note: "Vitals", fields: BASIC },
  { title: "Urine", note: "Urinalysis", fields: URINE },
  { title: "Blood", note: "Serum & hematology", fields: BLOOD },
  { title: "Medical history", note: "Comorbidities", fields: HISTORY },
];

const RISK_STYLES: Record<string, { text: string; bg: string; border: string }> = {
  LOW: { text: "text-[var(--risk-low)]", bg: "bg-[var(--risk-low)]/8", border: "border-[var(--risk-low)]/30" },
  MEDIUM: { text: "text-[var(--risk-medium)]", bg: "bg-[var(--risk-medium)]/8", border: "border-[var(--risk-medium)]/30" },
  HIGH: { text: "text-[var(--risk-high)]", bg: "bg-[var(--risk-high)]/8", border: "border-[var(--risk-high)]/30" },
};

const TABS = [
  { key: "dashboard", label: "Dashboard" },
  { key: "screening", label: "Screening" },
  { key: "scan", label: "Scan document" },
  { key: "imaging", label: "Imaging" },
  { key: "specialists", label: "Find specialists" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

export default function Home() {
  const [tab, setTab] = useState<TabKey>("dashboard");
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  function setField(key: string, value: string) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  function applyOCRValues(ocrValues: Record<string, string>) {
    setValues((v) => ({ ...v, ...ocrValues }));
    setTab("screening");
  }

  function buildPayload(): PredictionPayload {
    const payload: PredictionPayload = {};
    for (const [k, v] of Object.entries(values)) {
      if (v === "" || v === undefined) continue;
      const isNumeric = [...BASIC, ...URINE, ...BLOOD].some((f) => f.key === k && f.type === "number");
      payload[k] = isNumeric ? Number(v) : v;
    }
    return payload;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await predictCKD(buildPayload());
      setResult(res);
      addScreeningRecord(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong generating this screening estimate.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleDownloadReport() {
    setReportLoading(true);
    setReportError(null);
    try {
      await downloadReport("Not specified", buildPayload());
    } catch (err) {
      setReportError(err instanceof ApiError ? err.message : "Could not generate the report.");
    } finally {
      setReportLoading(false);
    }
  }

  function loadSample(kind: "high" | "low") {
    if (kind === "high") {
      setValues({
        age: "62", bp: "80", sg: "1.01", al: "2", su: "3",
        rbc: "normal", pc: "normal", pcc: "notpresent", ba: "notpresent",
        bgr: "423", bu: "53", sc: "1.8", hemo: "9.6", pcv: "31", wc: "7500",
        htn: "no", dm: "yes", cad: "no", appet: "poor", pe: "no", ane: "yes",
      });
    } else {
      setValues({
        age: "35", bp: "70", sg: "1.025", al: "0", su: "0",
        rbc: "normal", pc: "normal", pcc: "notpresent", ba: "notpresent",
        bgr: "95", bu: "20", sc: "0.8", hemo: "15.5", pcv: "48", wc: "6000",
        htn: "no", dm: "no", cad: "no", appet: "good", pe: "no", ane: "no",
      });
    }
    setResult(null);
    setError(null);
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-[var(--line)] bg-[var(--surface)]">
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[var(--primary)] flex items-center justify-center">
              <span className="font-[family-name:var(--font-display)] text-white text-sm font-bold">R</span>
            </div>
            <div>
              <div className="font-[family-name:var(--font-display)] font-semibold text-lg leading-none">RenalAI</div>
              <div className="text-xs text-[var(--ink-soft)] leading-none mt-1">CKD Screening Assistant</div>
            </div>
          </div>
          <span className="text-xs font-[family-name:var(--font-mono)] px-2.5 py-1 rounded-full border border-[var(--line)] text-[var(--ink-soft)]">
            prototype
          </span>
        </div>
        <nav className="max-w-5xl mx-auto px-6 flex gap-1 -mb-px overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`text-sm px-4 py-2.5 border-b-2 whitespace-nowrap transition-colors ${
                tab === t.key
                  ? "border-[var(--primary)] text-[var(--primary)] font-medium"
                  : "border-transparent text-[var(--ink-soft)] hover:text-[var(--ink)]"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10">
        {tab === "dashboard" && (
          <PatientDashboard latestResult={result} onNavigate={(t) => setTab(t)} />
        )}

        {tab === "screening" && (
          <div className="grid lg:grid-cols-[1fr_360px] gap-8 items-start">
            <section>
              <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight mb-2">
                Chronic kidney disease screening
              </h1>
              <p className="text-[var(--ink-soft)] mb-6 max-w-xl">
                Enter available clinical values below, or scan a lab report in the{" "}
                <button onClick={() => setTab("scan")} className="text-[var(--primary)] underline underline-offset-2">
                  Scan document
                </button>{" "}
                tab. Missing labs are fine.
              </p>

              <div className="flex gap-2 mb-6">
                <button type="button" onClick={() => loadSample("high")} className="text-xs font-medium px-3 py-1.5 rounded-full border border-[var(--line)] hover:border-[var(--primary)] transition-colors">
                  Load sample: high-risk profile
                </button>
                <button type="button" onClick={() => loadSample("low")} className="text-xs font-medium px-3 py-1.5 rounded-full border border-[var(--line)] hover:border-[var(--primary)] transition-colors">
                  Load sample: low-risk profile
                </button>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
                {PANELS.map((panel) => (
                  <fieldset key={panel.title} className="bg-[var(--surface)] border border-[var(--line)] rounded-xl p-5">
                    <legend className="px-1 -ml-1">
                      <span className="font-[family-name:var(--font-display)] font-semibold text-sm">{panel.title}</span>
                      <span className="text-xs text-[var(--ink-soft)] ml-2">{panel.note}</span>
                    </legend>
                    <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4 mt-2">
                      {panel.fields.map((f) => (
                        <label key={f.key} className="flex flex-col gap-1.5">
                          <span className="text-xs text-[var(--ink-soft)]">
                            {f.label}
                            {f.unit ? <span className="opacity-70"> ({f.unit})</span> : null}
                          </span>
                          {f.type === "select" ? (
                            <select
                              value={values[f.key] ?? ""}
                              onChange={(e) => setField(f.key, e.target.value)}
                              className="border border-[var(--line)] rounded-lg px-3 py-2 text-sm bg-white font-[family-name:var(--font-mono)]"
                            >
                              <option value="">—</option>
                              {f.options!.map((o) => (
                                <option key={o} value={o}>{o}</option>
                              ))}
                            </select>
                          ) : (
                            <input
                              type="number"
                              step={f.step ?? "1"}
                              placeholder={f.placeholder}
                              value={values[f.key] ?? ""}
                              onChange={(e) => setField(f.key, e.target.value)}
                              className="border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-[family-name:var(--font-mono)]"
                            />
                          )}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                ))}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full sm:w-auto px-6 py-3 rounded-lg bg-[var(--primary)] text-white font-medium text-sm hover:bg-[var(--primary-dark)] transition-colors disabled:opacity-60"
                >
                  {loading ? "Running screening model…" : "Run CKD screening"}
                </button>
              </form>
            </section>

            <aside className="lg:sticky lg:top-6 space-y-4">
              <div className="bg-[var(--surface)] border border-[var(--line)] rounded-xl p-6 flex flex-col items-center text-center">
                <KidneyPulse risk={result?.risk_category ?? null} />
                {!result && !error && (
                  <p className="text-sm text-[var(--ink-soft)] mt-4">
                    Fill in the panel and run a screening to see a result here.
                  </p>
                )}
                {error && (
                  <div className="mt-4 text-sm text-[var(--risk-high)] bg-[var(--risk-high)]/8 border border-[var(--risk-high)]/30 rounded-lg p-3">
                    {error}
                  </div>
                )}
                {result && (
                  <div className="mt-4 w-full text-left">
                    <div className={`rounded-lg border px-4 py-3 mb-4 ${RISK_STYLES[result.risk_category].bg} ${RISK_STYLES[result.risk_category].border}`}>
                      <div className={`font-[family-name:var(--font-display)] font-semibold text-lg ${RISK_STYLES[result.risk_category].text}`}>
                        {result.risk_category} RISK
                      </div>
                      <div className="text-sm text-[var(--ink-soft)]">
                        {result.prediction === "ckd" ? "Pattern consistent with CKD" : "Pattern not consistent with CKD"}
                        {" · "}
                        <span className="font-[family-name:var(--font-mono)]">{(result.probability_ckd * 100).toFixed(1)}%</span>
                      </div>
                    </div>

                    <div className="text-xs uppercase tracking-wide text-[var(--ink-soft)] mb-2">Top contributing factors</div>
                    <ul className="space-y-1.5 mb-4">
                      {result.top_contributing_features.map((f) => (
                        <li key={f.feature} className="flex items-center justify-between text-sm">
                          <span className="capitalize">{f.feature}</span>
                          <span className={`font-[family-name:var(--font-mono)] text-xs ${f.direction.includes("increase") ? "text-[var(--risk-high)]" : "text-[var(--risk-low)]"}`}>
                            {f.direction.includes("increase") ? "↑" : f.direction.includes("decrease") ? "↓" : "•"}
                          </span>
                        </li>
                      ))}
                    </ul>

                    <p className="text-xs text-[var(--ink-soft)] leading-relaxed border-t border-[var(--line)] pt-3 mb-3">
                      {result.clinical_explanation}
                    </p>

                    <button
                      onClick={handleDownloadReport}
                      disabled={reportLoading}
                      className="w-full text-sm font-medium px-4 py-2 rounded-lg border border-[var(--primary)] text-[var(--primary)] hover:bg-[var(--primary)] hover:text-white transition-colors disabled:opacity-60"
                    >
                      {reportLoading ? "Generating PDF…" : "Download PDF report"}
                    </button>
                    {reportError && <p className="text-xs text-[var(--risk-high)] mt-2">{reportError}</p>}
                  </div>
                )}
              </div>

              <p className="text-[11px] text-[var(--ink-soft)] leading-relaxed px-1">
                RenalAI is a screening-support prototype, not a diagnostic device. It is not
                a substitute for clinical judgment, laboratory confirmation, or evaluation by
                a licensed nephrologist.
              </p>
            </aside>
          </div>
        )}

        {tab === "scan" && (
          <div className="max-w-xl">
            <h1 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight mb-2">
              Scan a lab report
            </h1>
            <p className="text-[var(--ink-soft)] mb-6 text-sm">
              Extracted values are shown for your review, then applied to the screening form —
              nothing is submitted automatically.
            </p>
            <OCRScanner onApply={applyOCRValues} />
          </div>
        )}

        {tab === "imaging" && (
          <div className="max-w-xl">
            <h1 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight mb-2">
              Medical imaging
            </h1>
            <p className="text-[var(--ink-soft)] mb-6 text-sm">
              CT, MRI, and ultrasound upload architecture — separate from the CKD prediction model.
            </p>
            <ImagingUpload />
          </div>
        )}

        {tab === "specialists" && (
          <div className="max-w-xl">
            <h1 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight mb-2">
              Find nearby specialists
            </h1>
            <p className="text-[var(--ink-soft)] mb-6 text-sm">
              Search nephrologists, kidney hospitals, dialysis centers, and emergency hospitals near you.
            </p>
            <NearbySpecialists />
          </div>
        )}
      </main>

      <ChatWidget />
    </div>
  );
}
