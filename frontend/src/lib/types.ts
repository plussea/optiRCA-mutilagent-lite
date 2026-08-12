export type SessionStatus =
  | "init"
  | "perception_running"
  | "diagnosis_running"
  | "validation_running"
  | "planning_running"
  | "solution_validation_running"
  | "human_review_running"
  | "closure_running"
  | "perceived"
  | "diagnosed"
  | "diagnosis_validated"
  | "planned"
  | "solution_validated"
  | "waiting_review"
  | "closed"
  | "rejected"
  | "escalated"
  | "error";

export interface SessionState {
  session_id: string;
  status: SessionStatus;
  pending_human: boolean;
  human_decision?: string | null;
  perception?: Record<string, any>;
  diagnosis?: Record<string, any>;
  validation?: Record<string, any>;
  planning?: Record<string, any>;
  solution_validation?: Record<string, any>;
  human_review?: Record<string, any>;
  closure?: Record<string, any>;
  observations?: Array<Record<string, any>>;
  tool_calls?: Array<Record<string, any>>;
  decision_trace?: Array<Record<string, any>>;
  error_message?: string | null;
}

export interface WorkflowEvent {
  phase: string;
  payload: Record<string, any>;
  created_at: string;
}

// ---- New /api/v1/diagnose types -------------------------------------------------

export interface EvidenceNode {
  id: string;
  type: "Device" | "Port" | "Link" | "Alarm" | "Service";
  device_id?: string;
  port_id?: string;
  link_id?: string;
  alarm_id?: string;
  service_id?: string;
  alarm_type?: string;
  severity?: string;
  timestamp?: string;
  direction?: "in" | "out";
  endpoint_a?: string;
  endpoint_b?: string;
  length_km?: number;
  inferred?: boolean;
  isolated?: boolean;
  confidence?: number;
  [key: string]: any;
}

export interface EvidenceEdge {
  source: string;
  target: string;
  type: "BELONGS_TO" | "TOPOLOGY" | "PROPAGATES" | "CARRIES";
  confidence?: number;
  distance_km?: number;
  latency_ms?: number;
  probability?: number;
  delay_ms?: number;
  [key: string]: any;
}

export interface EvidenceGraph {
  nodes: EvidenceNode[];
  edges: EvidenceEdge[];
}

export interface RootCauseCandidate {
  root_cause: string;
  confidence: number;
  score_vector: number[];
  evidence_chain: string[];
  llm_enriched?: boolean;
  validation?: {
    direction_check: boolean;
    time_check: boolean;
    coverage_check: boolean;
  };
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
    topology?: Record<string, any>;
  };
  evidence_graph: EvidenceGraph;
  critic_verdict: "pass" | "reject" | null;
  metadata?: {
    phases_completed?: string[];
    fallback_rounds?: number;
    diagnosed_at?: string;
  };
  degradation_reason?: string;
  error?: string | null;
}

export interface Dossier {
  dossier_id: string;
  session_id: string;
  input_layer: {
    filename?: string;
    topology?: Record<string, any>;
    submitted_at?: string;
  };
  intermediate_layer: {
    hypotheses: RootCauseCandidate[];
    validation_results: any[];
    scores: number[][];
    critic_challenges: any[];
    evidence_graph: EvidenceGraph;
  };
  output_layer: {
    root_cause: RootCauseCandidate | null;
    confidence: number;
    requires_human_review: boolean;
    suggested_action: string;
  };
  feedback_layer: {
    human_decision?: string | null;
    human_notes?: string | null;
    ground_truth?: Record<string, any> | null;
  };
  metadata: {
    critic_verdict?: string | null;
    degradation_reason?: string | null;
    archived_at?: string;
  };
}
