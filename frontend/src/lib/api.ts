import type { DiagnosisResult, Dossier } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8010";

export async function diagnose(alarms: File, topology: object): Promise<DiagnosisResult> {
  const form = new FormData();
  form.append("alarms", alarms);
  form.append("topology", JSON.stringify(topology));

  const response = await fetch(`${API_URL}/api/v1/diagnose`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function fetchDossier(dossierId: string): Promise<Dossier> {
  const response = await fetch(`${API_URL}/v1/dossier/${dossierId}`);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function submitDecision(
  sessionId: string,
  decision: "approved" | "rejected" | "escalated",
  notes: string,
): Promise<{ session_id: string; status: string }> {
  const form = new FormData();
  form.append("decision", decision);
  form.append("notes", notes);
  const response = await fetch(`${API_URL}/v1/sessions/${sessionId}/human-decision`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}
