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
}

export interface TrendResult {
  profit: number;
  trend: 'growing' | 'stable' | 'shrinking';
  insight: string;
}

export interface BenchmarkResult {
  benchmark_result: string;
  comparison_insight: string;
}

export type DecisionStatus = 'APPROVED' | 'REJECTED' | 'FLAGGED' | 'PENDING';

export interface UnderwritingResult {
  risk_score: number;
  decision_status: DecisionStatus;
  agent_logs: string[];
  audit: AuditResult;
  trend: TrendResult;
  benchmark: BenchmarkResult;
  final_summary: string;
  crew_status: string;
  needs_hitl: boolean;
}

export interface AnalyzeRequest {
  data: FinancialData;
  region: string;
  human_response?: string;
}
