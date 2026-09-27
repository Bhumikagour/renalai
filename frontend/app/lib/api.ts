export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface PredictionPayload {
  [key: string]: string | number | undefined;
}

export interface TopFeature {
  feature: string;
  impact: number;
  direction: string;
}

export interface PredictionResult {
  prediction: "ckd" | "notckd";
  probability_ckd: number;
  risk_category: "LOW" | "MEDIUM" | "HIGH";
  top_contributing_features: TopFeature[];
  explanation_method: string;
  clinical_explanation: string;
  disclaimer: string;
}

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
}

export async function predictCKD(payload: PredictionPayload): Promise<PredictionResult> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/predictions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiError(
      "Can't reach the RenalAI prediction service. Is the backend running?"
    );
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status);
  }

  return res.json();
}

// ---- OCR ----
export interface OCRField {
  value: string | number;
  matched_text: string;
  confidence: "medium" | "low";
  flag?: string | null;
}
export interface OCRResult {
  document_id: string;
  raw_text: string;
  extracted_fields: Record<string, OCRField>;
  fields_found?: number;
  fields_total?: number;
  warning?: string | null;
}

export async function scanDocument(file: File): Promise<OCRResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/ocr/scan`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body?.detail || `OCR failed (${res.status})`, res.status);
  }
  return res.json();
}

// ---- PDF report ----
export async function downloadReport(
  patientName: string,
  clinicalData: PredictionPayload,
  doctorNotes?: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/reports/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patient_name: patientName, clinical_data: clinicalData, doctor_notes: doctorNotes }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body?.detail || `Report generation failed (${res.status})`, res.status);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "renalai-report.pdf";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ---- Chat ----
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}
export interface ChatResponse {
  available: boolean;
  reply?: string | null;
  error?: string | null;
}

export async function getChatStatus(): Promise<{ available: boolean }> {
  const res = await fetch(`${API_BASE}/chat/status`);
  if (!res.ok) return { available: false };
  return res.json();
}

export async function sendChatMessage(message: string, history: ChatMessage[]): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!res.ok) {
    return { available: false, error: `Request failed (${res.status})` };
  }
  return res.json();
}

// ---- Imaging ----
export interface GradCAMResult {
  available: boolean;
  overlay_base64: string | null;
  backbone?: string;
  backbone_top_class_index?: number;
  backbone_confidence?: number;
  note: string;
}

export interface ImagingResult {
  image_id: string;
  modality: string;
  preprocessing_ok: boolean;
  label: string;
  result: {
    status: string;
    confidence: number | null;
    predicted_class: string | null;
    gradcam_available: boolean;
    message: string;
  };
  gradcam?: GradCAMResult;
}

export async function uploadImagingScan(file: File, modality: string): Promise<ImagingResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("modality", modality);
  const res = await fetch(`${API_BASE}/imaging/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body?.detail || `Imaging upload failed (${res.status})`, res.status);
  }
  return res.json();
}

// ---- Location ----
export interface NearbyPlace {
  name: string;
  address: string;
  rating: number | null;
  user_ratings_total: number | null;
  open_now: boolean | null;
}

export async function getLocationStatus(): Promise<{ available: boolean }> {
  const res = await fetch(`${API_BASE}/location/status`);
  if (!res.ok) return { available: false };
  return res.json();
}

export async function findNearby(
  latitude: number,
  longitude: number,
  category: string
): Promise<{ category: string; results: NearbyPlace[] }> {
  const params = new URLSearchParams({ latitude: String(latitude), longitude: String(longitude), category });
  const res = await fetch(`${API_BASE}/location/nearby?${params.toString()}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body?.detail || `Location search failed (${res.status})`, res.status);
  }
  return res.json();
}
