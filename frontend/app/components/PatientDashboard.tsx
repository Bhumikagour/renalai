"use client";

import { useEffect, useState } from "react";
import KidneyPulse from "./KidneyPulse";
import { PredictionResult } from "../lib/api";
import {
  getScreeningHistory,
  getImagingHistory,
  ScreeningHistoryEntry,
  ImagingHistoryEntry,
} from "../lib/history";

type TabKey = "dashboard" | "screening" | "scan" | "imaging" | "specialists";

const RISK_STYLES: Record<string, { text: string; bg: string; border: string }> = {
  LOW: { text: "text-[var(--risk-low)]", bg: "bg-[var(--risk-low)]/8", border: "border-[var(--risk-low)]/30" },
  MEDIUM: { text: "text-[var(--risk-medium)]", bg: "bg-[var(--risk-medium)]/8", border: "border-[var(--risk-medium)]/30" },
  HIGH: { text: "text-[var(--risk-high)]", bg: "bg-[var(--risk-high)]/8", border: "border-[var(--risk-high)]/30" },
};

const RISK_BAR: Record<string, string> = {
  LOW: "bg-[var(--risk-low)]",
  MEDIUM: "bg-[var(--risk-medium)]",
  HIGH: "bg-[var(--risk-high)]",
};

const QUICK_ACTIONS: { key: TabKey; icon: string; title: string; note: string }[] = [
  { key: "screening", icon: "🩺", title: "Run a screening", note: "Enter labs & vitals for a fresh estimate" },
  { key: "scan", icon: "🧾", title: "Scan a lab report", note: "Auto-fill values from a photo or PDF" },
  { key: "imaging", icon: "🧠", title: "Upload imaging", note: "CT / MRI / USG + Grad-CAM explainability" },
  { key: "specialists", icon: "📍", title: "Find specialists", note: "Nephrologists & dialysis centers nearby" },
];

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function PatientDashboard({
  latestResult,
  onNavigate,
}: {
  latestResult: PredictionResult | null;
  onNavigate: (tab: TabKey) => void;
}) {
  const [screeningHistory, setScreeningHistory] = useState<ScreeningHistoryEntry[]>([]);
  const [imagingHistory, setImagingHistory] = useState<ImagingHistoryEntry[]>([]);

  useEffect(() => {
    setScreeningHistory(getScreeningHistory());
    setImagingHistory(getImagingHistory());
  }, []);

  const lastFromHistory = screeningHistory[screeningHistory.length - 1];
  const snapshot: {
    risk_category: PredictionResult["risk_category"];
    probability_ckd: number;
    prediction: PredictionResult["prediction"];
  } | null = latestResult
    ? latestResult
    : lastFromHistory
    ? lastFromHistory
    : null;

  const trend = screeningHistory.slice(-6);
  const lastImaging = imagingHistory[imagingHistory.length - 1];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight mb-2">
          Your kidney health dashboard
        </h1>
        <p className="text-[var(--ink-soft)] max-w-xl text-sm">
          A quick snapshot of your screenings, imaging activity, and next steps. Recent
          activity below is stored on this device only.
        </p>
      </div>

      <div className="grid lg:grid-cols-[280px_1fr] gap-6">
        {/* Risk snapshot */}
        <div className="bg-[var(--surface)] border border-[var(--line)] rounded-xl p-6 flex flex-col items-center text-center">
          <KidneyPulse risk={snapshot?.risk_category ?? null} />
          {!snapshot && (
            <>
              <p className="text-sm text-[var(--ink-soft)] mt-4">
                You haven&apos;t run a screening yet on this device.
              </p>
              <button
                onClick={() => onNavigate("screening")}
                className="mt-4 w-full text-sm font-medium px-4 py-2 rounded-lg bg-[var(--primary)] text-white hover:bg-[var(--primary-dark)] transition-colors"
              >
                Run your first screening
              </button>
            </>
          )}
          {snapshot && (
            <div className="mt-4 w-full text-left">
              <div className={`rounded-lg border px-4 py-3 ${RISK_STYLES[snapshot.risk_category].bg} ${RISK_STYLES[snapshot.risk_category].border}`}>
                <div className={`font-[family-name:var(--font-display)] font-semibold text-lg ${RISK_STYLES[snapshot.risk_category].text}`}>
                  {snapshot.risk_category} RISK
                </div>
                <div className="text-sm text-[var(--ink-soft)]">
                  {snapshot.prediction === "ckd" ? "Pattern consistent with CKD" : "Pattern not consistent with CKD"}
                  {" · "}
                  <span className="font-[family-name:var(--font-mono)]">
                    {(snapshot.probability_ckd * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
              <button
                onClick={() => onNavigate("screening")}
                className="mt-3 w-full text-xs font-medium px-3 py-2 rounded-lg border border-[var(--line)] hover:border-[var(--primary)] transition-colors"
              >
                Run another screening
              </button>
            </div>
          )}
        </div>

        <div className="space-y-6">
          {/* Trend */}
          <div className="bg-[var(--surface)] border border-[var(--line)] rounded-xl p-5">
            <h3 className="font-[family-name:var(--font-display)] font-semibold text-sm mb-3">
              Screening trend
            </h3>
            {trend.length === 0 ? (
              <p className="text-xs text-[var(--ink-soft)]">
                Your last few screenings will appear here as a quick trend once you run one.
              </p>
            ) : (
              <div className="flex items-end gap-3 h-24">
                {trend.map((entry, i) => (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1.5">
                    <div className="w-full flex-1 flex items-end">
                      <div
                        className={`w-full rounded-t-sm ${RISK_BAR[entry.risk_category]}`}
                        style={{ height: `${Math.max(entry.probability_ckd * 100, 6)}%` }}
                        title={`${entry.risk_category} · ${(entry.probability_ckd * 100).toFixed(1)}%`}
                      />
                    </div>
                    <span className="text-[10px] text-[var(--ink-soft)] font-[family-name:var(--font-mono)] whitespace-nowrap">
                      {formatDate(entry.at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Imaging + voice assistant pointers */}
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="bg-[var(--surface)] border border-[var(--line)] rounded-xl p-5">
              <h3 className="font-[family-name:var(--font-display)] font-semibold text-sm mb-2">
                Imaging activity
              </h3>
              {lastImaging ? (
                <p className="text-xs text-[var(--ink-soft)] leading-relaxed">
                  {imagingHistory.length} scan{imagingHistory.length === 1 ? "" : "s"} uploaded on this device.
                  Last: <span className="font-[family-name:var(--font-mono)]">{lastImaging.modality.toUpperCase()}</span>{" "}
                  on {formatDate(lastImaging.at)}
                  {lastImaging.gradcam_available ? " · Grad-CAM heatmap generated" : ""}.
                </p>
              ) : (
                <p className="text-xs text-[var(--ink-soft)] leading-relaxed">
                  No scans uploaded yet. CT, MRI, and USG uploads get a Grad-CAM
                  explainability overlay.
                </p>
              )}
              <button
                onClick={() => onNavigate("imaging")}
                className="mt-3 text-xs font-medium px-3 py-1.5 rounded-full border border-[var(--line)] hover:border-[var(--primary)] transition-colors"
              >
                Go to imaging
              </button>
            </div>

            <div className="bg-[var(--surface)] border border-[var(--line)] rounded-xl p-5">
              <h3 className="font-[family-name:var(--font-display)] font-semibold text-sm mb-2">
                🎙️ Voice assistant
              </h3>
              <p className="text-xs text-[var(--ink-soft)] leading-relaxed">
                The chat bubble in the bottom-right corner now supports speaking your
                question and having replies read back to you — handy if typing isn&apos;t
                convenient.
              </p>
            </div>
          </div>

          {/* Quick actions */}
          <div>
            <h3 className="font-[family-name:var(--font-display)] font-semibold text-sm mb-3">
              Quick actions
            </h3>
            <div className="grid sm:grid-cols-2 gap-3">
              {QUICK_ACTIONS.map((a) => (
                <button
                  key={a.key}
                  onClick={() => onNavigate(a.key)}
                  className="text-left bg-[var(--surface)] border border-[var(--line)] rounded-xl p-4 hover:border-[var(--primary)] transition-colors flex items-start gap-3"
                >
                  <span className="text-xl leading-none">{a.icon}</span>
                  <span>
                    <span className="block text-sm font-medium">{a.title}</span>
                    <span className="block text-xs text-[var(--ink-soft)] mt-0.5">{a.note}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <p className="text-[11px] text-[var(--ink-soft)] leading-relaxed px-1">
        RenalAI is a screening-support prototype, not a diagnostic device. It is not a
        substitute for clinical judgment, laboratory confirmation, or evaluation by a
        licensed nephrologist.
      </p>
    </div>
  );
}
