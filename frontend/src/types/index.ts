export interface Transaction {
  date: string;
  description: string;
  amount: number;
  type: 'credit' | 'debit';
}

export interface FinancialData {
  applicant_id?: string;
  statement_month?: string;
  transactions: Transaction[];
  total_inflow: number;
  total_outflow: number;
}

export interface AuditResult {
  risk_score: number;
  flags: string[];
  explanation: string;
  mode?: 'llm' | 'deterministic_fallback' | 'deterministic';
  llm_error?: string | null;
}

export interface TrendResult {
  profit: number;
  trend: 'growing' | 'stable' | 'shrinking';
  insight: string;
  mode?: 'llm' | 'deterministic_fallback' | 'deterministic';
  llm_error?: string | null;
}

export interface BenchmarkResult {
  benchmark_result: string;
  comparison_insight: string;
  mode?: 'llm' | 'deterministic_fallback' | 'deterministic';
  llm_error?: string | null;
}

export interface CommitteeChairResult {
  final_verdict_rationale: string;
  key_supporting_points: string[];
  key_risks: string[];
  confidence: number;
  conditions_if_approved: string[];
  mode?: 'llm' | 'deterministic_fallback' | 'deterministic_guardrail' | 'deterministic';
  llm_error?: string | null;
}

export type DecisionStatus = 'APPROVED' | 'REJECTED' | 'FLAGGED' | 'PENDING';

export interface UnderwritingResult {
  risk_score: number;
  decision_status: DecisionStatus;
  agent_logs: string[];
  audit: AuditResult;
  trend: TrendResult;
  benchmark: BenchmarkResult;
  committee_chair: CommitteeChairResult;
  final_summary: string;
  crew_status: string;
  crew_mode?: 'llm' | 'deterministic';
  needs_hitl: boolean;
}

export interface AnalyzeRequest {
  data: FinancialData;
  region: string;
  human_response?: string;
  thread_id?: string;
}

export interface PersistenceDebug {
  cases_count: number;
  last_case_id?: string | null;
  last_case_timestamp?: string | null;
  last_checkpoint_decision_status?: string | null;
  last_checkpoint_risk_score?: number | null;
}

export interface CompanyCaseSummary {
  company_id: string;
  company_name: string;
  case_id?: string | null;
  case_status?: string | null;
  doc_types: string[];
}

export interface IngestResponse {
  case_id: string;
  company_id: string;
  status: string;
  files_received: number;
  message: string;
  /** Present when the API creates document rows before queuing extraction. */
  document_ids?: string[];
}

export interface CaseDocument {
  document_id: string;
  document_name: string;
  doc_type?: string | null;
  metadata: Record<string, unknown>;
  extracted_data: Record<string, unknown>;
  status: string;
  created_at?: string | null;
}

/** NDJSON progress line from ``POST /api/underwrite/stream``. */
export interface FlowProgressPayload {
  type: 'progress';
  phase: string;
  step: string;
  label: string;
  active_index: number;
  route?: string;
  skipped_steps?: string[];
  human_in_loop?: boolean;
}

export interface LangGraphFlowResponse {
  status: 'COMPLETED' | 'NEEDS_INPUT';
  thread_id: string;
  active_index: number;
  label: string;
  logs: string[];
  decision: DecisionStatus;
  hitl_context?: {
    reason?: string;
    message?: string;
    threshold?: number;
    transaction?: {
      date?: string;
      description?: string;
      amount?: number;
      type?: 'credit' | 'debit' | string;
    };
  } | null;
  result?: UnderwritingResult | null;
}
