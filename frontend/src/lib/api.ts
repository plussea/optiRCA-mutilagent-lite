import type { SessionState, WorkflowEvent } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8010";

export async function createSession(file: File): Promise<{ session_id: string; status: string }> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_URL}/v1/sessions`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function fetchSession(sessionId: string): Promise<SessionState> {
  const response = await fetch(`${API_URL}/v1/sessions/${sessionId}`);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function fetchEvents(sessionId: string): Promise<WorkflowEvent[]> {
  const response = await fetch(`${API_URL}/v1/sessions/${sessionId}/events`);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const body = await response.json();
  return body.events ?? [];
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
