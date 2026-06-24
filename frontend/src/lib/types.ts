export type SessionStatus =
  | "init"
  | "perception_running"
  | "diagnosis_running"
  | "validation_running"
  | "planning_running"
  | "solution_validation_running"
  | "human_review_running"
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
