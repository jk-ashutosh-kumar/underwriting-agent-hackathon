import type { FinancialData, UnderwritingResult } from '@/types';
import { RiskGauge } from './RiskGauge';
import { AuditorCard, TrendCard, BenchmarkCard } from './AgentCard';
import { DecisionBanner } from './DecisionBanner';
import { AgentLogs } from './AgentLogs';
import { HITLPanel } from './HITLPanel';
import { InsightsCharts } from './InsightsCharts';
import { ParsedDataCharts } from './ParsedDataCharts';
import { Separator } from '@/components/ui/separator';

interface ResultsDashboardProps {
  result: UnderwritingResult;
  inputData: FinancialData | null;
  onHITLSubmit: (response: string) => void;
  loading: boolean;
}

export function ResultsDashboard({ result, inputData, onHITLSubmit, loading }: ResultsDashboardProps) {
  return (
    <div className="flex-1 space-y-5 min-w-0">
      {/* Risk + Decision row */}
      <div className="grid grid-cols-[auto_1fr] gap-4 items-stretch">
        {/* Risk Gauge */}
        <div className="rounded-xl border border-border/60 bg-elevated px-6 py-4 flex flex-col items-center justify-center gap-1">
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-semibold">Risk Score</p>
          <RiskGauge score={result.risk_score} />
        </div>
        {/* Decision Banner */}
        <DecisionBanner status={result.decision_status} finalSummary={result.final_summary} />
      </div>

      <InsightsCharts result={result} />
      {inputData && <ParsedDataCharts data={inputData} />}

      {/* HITL Panel */}
      {result.needs_hitl && result.decision_status === 'FLAGGED' && (
        <HITLPanel onSubmit={onHITLSubmit} loading={loading} />
      )}

      <Separator className="bg-border/30" />

      {/* Agent Cards */}
      <div>
        <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-semibold mb-3">
          Agent Committee Output
        </p>
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
          <AuditorCard data={result.audit} />
          <TrendCard data={result.trend} />
          <BenchmarkCard data={result.benchmark} />
        </div>
      </div>

      {/* Agent Logs */}
      <AgentLogs logs={result.agent_logs} />

      {/* Crew Status */}
      {result.crew_status && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border/40 bg-muted/10">
          <span className="w-1.5 h-1.5 rounded-full bg-primary" />
          <span className="text-xs text-muted-foreground font-mono">{result.crew_status}</span>
        </div>
      )}
    </div>
  );
}
