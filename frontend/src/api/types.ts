// ProtoFlow API types — mirrors backend Pydantic contracts

export type StageStatus =
  | "pending"
  | "running"
  | "complete"
  | "failed"
  | "repair_triggered"
  | "hitl_required";

export interface StageUpdateEvent {
  event: "stage_update";
  session_id: string;
  stage: string;
  status: StageStatus;
  model: string;
  latency_ms: number;
  confidence?: number;
  tokens_used: number;
  output_summary: string;
  assumptions: string[];
  conflicts: string[];
}

export interface HITLRequiredEvent {
  event: "hitl_required";
  session_id: string;
  stage: string;
  trigger_reason: string;
  questions: string[];
  options: string[] | null;
  timeout_seconds: number;
}

export interface LogUpdateEvent {
  event: "log_update";
  session_id: string;
  content: string;
}

export interface MermaidDiagrams {
  pipeline_flow: string;
  er_diagram: string;
  api_sequence: string;
}

export interface PipelineCompleteEvent {
  event: "pipeline_complete";
  session_id: string;
  total_latency_ms: number;
  total_tokens: number;
  repair_count: number;
  hitl_count: number;
  final_schema: Record<string, unknown>;
  mermaid_diagrams: MermaidDiagrams;
  assumptions: string[];
  conflicts: Array<{ description: string; resolution_strategy: string }>;
}

export interface PipelineFailedEvent {
  event: "pipeline_failed";
  session_id: string;
  error: string;
}

export type SSEEvent =
  | StageUpdateEvent
  | HITLRequiredEvent
  | LogUpdateEvent
  | PipelineCompleteEvent
  | PipelineFailedEvent;

// Stage display metadata
export const STAGE_META: Record<string, { label: string; model: string }> = {
  intent_extraction:    { label: "Intent Extraction",    model: "qwen3-coder" },
  architecture_design:  { label: "Architecture Design",  model: "deepseek-v4-flash" },
  db_schema:            { label: "DB Schema",            model: "deepseek-v4-flash" },
  api_schema:           { label: "API Schema",           model: "deepseek-v4-flash" },
  ui_schema:            { label: "UI Schema",            model: "qwen3-coder" },
  auth_schema:          { label: "Auth Schema",          model: "gpt-oss-20b" },
  validation:           { label: "Validation",           model: "deepseek-v4-flash" },
  repair:               { label: "Repair",               model: "qwen3-coder" },
  runtime_validation:   { label: "Runtime Validation",   model: "gpt-oss-20b" },
  logging:              { label: "Logging & Diagrams",   model: "gpt-oss-20b" },
};

export const STAGE_ORDER = Object.keys(STAGE_META);
