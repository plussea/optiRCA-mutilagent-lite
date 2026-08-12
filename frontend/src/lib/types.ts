export type WorkbenchStatus =
  | "idle"
  | "preflighting"
  | "ready"
  | "input_not_ready"
  | "running"
  | "success"
  | "degraded"
  | "cancelled"
  | "error";

export interface Device {
  device_id: string;
  type?: string;
}

export interface Port {
  port_id: string;
  device_id: string;
  direction?: "in" | "out" | null;
}

export interface TopologyLink {
  link_id: string;
  endpoint_a: string;
  endpoint_b: string;
  length_km?: number;
  confidence?: number;
  inferred?: boolean;
  inference_explanation?: string;
}

export interface BusinessTopology {
  source: "provided" | "inferred";
  confidence: number;
  devices: Device[];
  ports: Port[];
  links: TopologyLink[];
  inference_explanations?: string[];
}

export interface AlarmFact {
  alarm_id: string;
  type: string;
  device_id: string;
  port_id?: string;
  severity?: string;
  timestamp?: string;
  location?: string;
}

export interface SampleSummary {
  alarm_count: number;
  severity_counts: Record<string, number>;
  device_count: number;
  alarm_types: string[];
  time_window: { start: string | null; end: string | null };
}

export interface PreflightIssue {
  code: string;
  message: string;
  objects?: string[];
  required_fields?: string[];
}

export interface PreflightResult {
  status: "ready" | "input_not_ready";
  preflight_id: string;
  sample_summary: SampleSummary;
  topology: BusinessTopology;
  alarms: AlarmFact[];
  issues: PreflightIssue[];
}

export interface EvidenceNode {
  id: string;
  type: "Device" | "Port" | "Link" | "Alarm" | "Service";
  device_id?: string;
  port_id?: string;
  link_id?: string;
  alarm_id?: string;
  alarm_type?: string;
  severity?: string;
  timestamp?: string;
  [key: string]: unknown;
}

export interface EvidenceEdge {
  source: string;
  target: string;
  type: "BELONGS_TO" | "TOPOLOGY" | "PROPAGATES" | "CARRIES";
  confidence?: number;
  [key: string]: unknown;
}

export interface EvidenceGraph {
  nodes: EvidenceNode[];
  edges: EvidenceEdge[];
}

export interface RootCauseCandidate {
  root_cause: string;
  confidence: number;
  score_vector?: number[];
  evidence_chain: string[];
  validation?: {
    direction_check: boolean;
    time_check: boolean;
    coverage_check: boolean;
  };
}

export interface CredibilityCheck {
  id: string;
  label: string;
  passed: boolean;
  reason: string;
}

export interface DiagnosisResult {
  status: "success" | "degraded";
  dossier_id: string;
  session_id: string;
  root_cause: RootCauseCandidate | Record<string, never>;
  evidence_chain: string[];
  confidence: number;
  suggestion: string;
  requires_human_review: boolean;
  input: {
    filename?: string;
    preflight_id?: string;
    topology?: BusinessTopology;
    topology_source?: string;
    topology_confidence?: number;
  };
  evidence_graph: EvidenceGraph;
  candidates?: RootCauseCandidate[];
  critic_checks?: CredibilityCheck[];
  critic_verdict: "pass" | "reject" | null;
  metadata?: {
    phases_completed?: string[];
    fallback_rounds?: number;
    diagnosed_at?: string;
  };
  degradation_reason?: string;
  error?: string | null;
}

export type StageId = "perception" | "topology" | "judge" | "rank" | "critic" | "dossier";

export type DiagnosisEvent =
  | { type: "diagnosis.started"; timestamp: string; preflight_id?: string }
  | { type: "stage.started"; stage: StageId; timestamp: string }
  | {
      type: "stage.completed";
      stage: StageId;
      timestamp: string;
      elapsed_ms: number;
      summary: string;
      artifact?: Record<string, unknown>;
    }
  | { type: "topology.updated"; timestamp: string; topology: BusinessTopology }
  | { type: "candidates.updated"; timestamp: string; candidates: RootCauseCandidate[] }
  | {
      type: "critic.checked";
      timestamp: string;
      checks: CredibilityCheck[];
      verdict?: string;
      fallback_action?: string | null;
    }
  | { type: "diagnosis.completed"; timestamp: string; result: DiagnosisResult }
  | { type: "diagnosis.degraded"; timestamp: string; result: DiagnosisResult }
  | { type: "diagnosis.cancelled"; timestamp: string }
  | { type: "human.reviewed"; timestamp: string; review: ReviewState };

export interface ReviewState {
  status: "unreviewed" | "confirmed" | "corrected" | "expert_review_requested";
  ground_truth?: { root_cause: string } | null;
  notes?: string;
  reviewed_at?: string;
}

export interface DiagnosisSession {
  session_id: string;
  status: "running" | "success" | "degraded" | "cancelled";
  preflight_id?: string;
  dossier_id?: string | null;
  result?: DiagnosisResult | null;
  review: ReviewState;
  input?: DiagnosisResult["input"];
  events_url: string;
}

export interface DemoExample {
  alarm_filename: string;
  alarm_content: string;
  topology_filename: string;
  topology: BusinessTopology;
  expected: {
    root_cause: string;
    minimum_alarm_coverage: number;
    expected_affected_devices: string[];
  };
}

export interface Dossier {
  dossier_id: string;
  session_id: string;
  input_layer: { filename?: string; topology?: BusinessTopology; submitted_at?: string };
  intermediate_layer: {
    hypotheses: RootCauseCandidate[];
    evidence_graph: EvidenceGraph;
  };
  output_layer: {
    root_cause: RootCauseCandidate | null;
    confidence: number;
    requires_human_review: boolean;
  };
  feedback_layer: {
    human_decision?: string | null;
    human_notes?: string | null;
    ground_truth?: { root_cause: string } | null;
  };
  metadata: {
    critic_verdict?: string | null;
    degradation_reason?: string | null;
    archived_at?: string;
  };
}
