// RenalAI has no patient database yet (see backend README) -- the dashboard's
// recent-activity view is backed by localStorage on this device only. This is
// explicitly a lightweight MVP shim, not a clinical record store.
import { PredictionResult, ImagingResult } from "./api";

const SCREENING_KEY = "renalai_screening_history";
const IMAGING_KEY = "renalai_imaging_history";
const MAX_ENTRIES = 10;

export interface ScreeningHistoryEntry {
  at: string; // ISO timestamp
  risk_category: PredictionResult["risk_category"];
  probability_ckd: number;
  prediction: PredictionResult["prediction"];
}

export interface ImagingHistoryEntry {
  at: string;
  modality: string;
  gradcam_available: boolean;
}

function safeRead<T>(key: string): T[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T[]) : [];
  } catch {
    return [];
  }
}

function safeWrite<T>(key: string, entries: T[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(entries.slice(-MAX_ENTRIES)));
  } catch {
    // ignore quota/serialization errors -- history is a convenience, not critical
  }
}

export function addScreeningRecord(result: PredictionResult) {
  const entries = safeRead<ScreeningHistoryEntry>(SCREENING_KEY);
  entries.push({
    at: new Date().toISOString(),
    risk_category: result.risk_category,
    probability_ckd: result.probability_ckd,
    prediction: result.prediction,
  });
  safeWrite(SCREENING_KEY, entries);
}

export function getScreeningHistory(): ScreeningHistoryEntry[] {
  return safeRead<ScreeningHistoryEntry>(SCREENING_KEY);
}

export function addImagingRecord(result: ImagingResult) {
  const entries = safeRead<ImagingHistoryEntry>(IMAGING_KEY);
  entries.push({
    at: new Date().toISOString(),
    modality: result.modality,
    gradcam_available: !!result.gradcam?.available,
  });
  safeWrite(IMAGING_KEY, entries);
}

export function getImagingHistory(): ImagingHistoryEntry[] {
  return safeRead<ImagingHistoryEntry>(IMAGING_KEY);
}
