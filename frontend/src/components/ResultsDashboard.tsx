import type { FinancialData, UnderwritingResult } from '@/types';
import { RiskGauge } from './RiskGauge';
import { AuditorCard, TrendCard, BenchmarkCard } from './AgentCard';
import { DecisionBanner } from './DecisionBanner';
import { AgentLogs } from './AgentLogs';
import { HITLPanel } from './HITLPanel';
import { InsightsCharts } from './InsightsCharts';
import { ParsedDataCharts } from './ParsedDataCharts';
import { AdvancedVisuals } from './AdvancedVisuals';
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
          <p className="text-[10px] text-muted-foreground/70">Lower is better</p>
          <RiskGauge score={result.risk_score} />
        </div>
        {/* Decision Banner */}
        <DecisionBanner status={result.decision_status} finalSummary={result.final_summary} />
      </div>

      <InsightsCharts result={result} />
      {inputData && <ParsedDataCharts data={inputData} />}
      <AdvancedVisuals result={result} inputData={inputData} />

      {/* HITL Panel */}
      {result.needs_hitl && result.decision_status === 'FLAGGED' && (
        <HITLPanel onSubmit={onHITLSubmit} loading={loading} />
      )}

      {/* Committee Chair */}
      <div className="rounded-xl border border-border/60 bg-elevated p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-semibold">
            Committee Chair Synthesis
          </p>
          <span className="text-xs font-mono text-muted-foreground">
            Confidence {result.committee_chair?.confidence ?? 0}%
          </span>
        </div>
        {result.committee_chair?.final_verdict_rationale && (
          <p className="text-sm text-foreground/90 leading-relaxed">
            {result.committee_chair.final_verdict_rationale}
          </p>
        )}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
          <div className="rounded-lg border border-success/25 bg-success/5 p-3">
            <p className="text-[10px] uppercase tracking-widest text-success/80 mb-2">Key Supporting Points</p>
            <ul className="text-xs text-foreground/85 space-y-1">
              {(result.committee_chair?.key_supporting_points ?? []).slice(0, 3).map((point, idx) => (
                <li key={idx}>• {point}</li>
              ))}
              {(result.committee_chair?.key_supporting_points ?? []).length === 0 && (
                <li className="text-muted-foreground">• No explicit supporting points returned.</li>
              )}
            </ul>
          </div>
          <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-3">
            <p className="text-[10px] uppercase tracking-widest text-destructive/80 mb-2">Key Risks</p>
            <ul className="text-xs text-foreground/85 space-y-1">
              {(result.committee_chair?.key_risks ?? []).slice(0, 3).map((point, idx) => (
                <li key={idx}>• {point}</li>
              ))}
              {(result.committee_chair?.key_risks ?? []).length === 0 && (
                <li className="text-muted-foreground">• No explicit risk points returned.</li>
              )}
            </ul>
          </div>
        </div>
        {(result.committee_chair?.conditions_if_approved ?? []).length > 0 && (
          <div className="rounded-lg border border-warning/25 bg-warning/5 p-3">
            <p className="text-[10px] uppercase tracking-widest text-warning/80 mb-2">Conditions If Approved</p>
            <ul className="text-xs text-foreground/85 space-y-1">
              {result.committee_chair.conditions_if_approved.map((condition, idx) => (
                <li key={idx}>• {condition}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

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

      {/* Orchestration note: backend always sets crew_status; hide the benign "all OK" line. */}
      {result.crew_status &&
        result.crew_status !== 'CrewAI committee configured with 3 agents and chained tasks.' && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border/40 bg-muted/10">
            <span className="w-1.5 h-1.5 rounded-full bg-primary" />
            <span className="text-xs text-muted-foreground font-mono">{result.crew_status}</span>
          </div>
        )}
    </div>
  );
}
