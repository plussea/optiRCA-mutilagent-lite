import type {
  DemoExample,
  DiagnosisEvent,
  DiagnosisSession,
  Dossier,
  PreflightResult,
  ReviewState,
} from "./types";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8010";

async function responseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `请求失败 (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function preflightSample(
  alarms: File,
  topology?: File | null,
): Promise<PreflightResult> {
  const form = new FormData();
  form.append("alarms", alarms);
  if (topology) form.append("topology_file", topology);
  return responseJson<PreflightResult>(
    await fetch(`${API_URL}/api/v1/preflight`, { method: "POST", body: form }),
  );
}

export async function startDiagnosis(preflightId: string): Promise<DiagnosisSession> {
  return responseJson<DiagnosisSession>(
    await fetch(`${API_URL}/api/v1/diagnoses`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preflight_id: preflightId, max_fallback_rounds: 2 }),
    }),
  );
}

export async function fetchDiagnosis(sessionId: string): Promise<DiagnosisSession> {
  return responseJson<DiagnosisSession>(
    await fetch(`${API_URL}/api/v1/diagnoses/${sessionId}`),
  );
}

export async function cancelDiagnosis(sessionId: string): Promise<void> {
  await responseJson(
    await fetch(`${API_URL}/api/v1/diagnoses/${sessionId}/cancel`, { method: "POST" }),
  );
}

export async function loadDemoExample(): Promise<DemoExample> {
  return responseJson<DemoExample>(await fetch(`${API_URL}/api/v1/examples/demo`));
}

export async function submitReview(
  sessionId: string,
  decision: "confirmed" | "corrected" | "expert_review_requested",
  notes: string,
  rootCause?: string,
): Promise<{ session_id: string; dossier_id: string; review: ReviewState }> {
  return responseJson(
    await fetch(`${API_URL}/api/v1/diagnoses/${sessionId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        decision,
        notes,
        ground_truth: decision === "corrected" && rootCause ? { root_cause: rootCause } : undefined,
      }),
    }),
  );
}

export function subscribeToDiagnosis(
  sessionId: string,
  onEvent: (event: DiagnosisEvent) => void,
  onError: () => void,
): () => void {
  const source = new EventSource(`${API_URL}/api/v1/diagnoses/${sessionId}/events`);
  source.onmessage = (message) => onEvent(JSON.parse(message.data) as DiagnosisEvent);
  source.onerror = onError;
  return () => source.close();
}

export async function fetchDiagnosisEvents(sessionId: string): Promise<DiagnosisEvent[]> {
  const response = await fetch(`${API_URL}/api/v1/diagnoses/${sessionId}/events`);
  if (!response.ok) throw new Error(await response.text());
  const text = await response.text();
  return text
    .split("\n")
    .filter((line) => line.startsWith("data: "))
    .map((line) => JSON.parse(line.slice(6)) as DiagnosisEvent);
}

export async function fetchDossier(dossierId: string): Promise<Dossier> {
  return responseJson<Dossier>(await fetch(`${API_URL}/v1/dossier/${dossierId}`));
}
