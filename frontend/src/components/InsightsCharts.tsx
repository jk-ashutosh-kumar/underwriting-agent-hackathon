import type { UnderwritingResult } from '@/types';
import { cn } from '@/lib/utils';
import { Activity, ShieldCheck, TrendingUp, TriangleAlert } from 'lucide-react';

interface InsightsChartsProps {
  result: UnderwritingResult;
}

function getDecisionConfidence(status: UnderwritingResult['decision_status']): number {
  if (status === 'APPROVED') return 86;
  if (status === 'REJECTED') return 81;
  if (status === 'FLAGGED') return 62;
  return 50;
}

function getRiskBand(score: number): string {
  if (score < 30) return 'Low';
  if (score < 60) return 'Medium';
  return 'High';
}

function buildMomentumPoints(profit: number, trend: UnderwritingResult['trend']['trend']): string {
  const base = [36, 44, 48, 52, 58];
  const trendShift = trend === 'growing' ? [0, 4, 8, 10, 14] : trend === 'shrinking' ? [0, -3, -7, -10, -14] : [0, 0, 1, 0, 0];
  const profitModifier = Math.max(-8, Math.min(8, Math.round(profit / 20000)));

  const points = base.map((y, idx) => y - trendShift[idx] - profitModifier);
  return points.map((y, idx) => `${10 + idx * 22},${y}`).join(' ');
}

export function InsightsCharts({ result }: InsightsChartsProps) {
  const risk = Math.max(0, Math.min(100, result.risk_score));
  const safe = 100 - risk;
  const confidence = getDecisionConfidence(result.decision_status);
  const flags = result.audit.flags.length;
  const highSeverity = Math.min(flags, 3);
  const mediumSeverity = Math.max(0, Math.min(flags - highSeverity, 2));
  const lowSeverity = Math.max(0, flags - highSeverity - mediumSeverity);
  const momentumPoints = buildMomentumPoints(result.trend.profit, result.trend.trend);

  return (
    <div className="rounded-2xl border border-border/60 bg-elevated p-6 shadow-sm space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground/80 font-semibold">
          Visual Insights
        </p>
        <span className="text-xs text-muted-foreground/70">live committee summary</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border/60 bg-muted/30 p-4 min-h-40 space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <ShieldCheck className="w-4 h-4 text-primary" />
            <span>Risk Composition</span>
          </div>
          <div className="flex items-center gap-4">
            <svg width="78" height="78" viewBox="0 0 42 42" className="-rotate-90">
              <circle cx="21" cy="21" r="15.915" fill="none" stroke="currentColor" strokeWidth="4" className="text-muted/40" />
              <circle
                cx="21"
                cy="21"
                r="15.915"
                fill="none"
                stroke="currentColor"
                strokeWidth="4"
                strokeDasharray={`${risk} ${safe}`}
                className={cn(risk < 30 ? 'text-success' : risk < 60 ? 'text-warning' : 'text-destructive')}
              />
            </svg>
            <div>
              <p className="text-xl font-mono font-bold">{risk}%</p>
              <p className="text-xs text-muted-foreground mt-1">{getRiskBand(risk)} exposure</p>
              <p className="text-[10px] text-muted-foreground/70 mt-0.5">Lower is better</p>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border/60 bg-muted/30 p-4 min-h-40 space-y-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Activity className="w-4 h-4 text-accent" />
            <span>Decision Confidence</span>
          </div>
          <div className="h-3 rounded-full bg-muted/50 overflow-hidden">
            <div
              className="h-full rounded-full bg-linear-to-r from-primary via-accent to-success transition-all duration-700"
              style={{ width: `${confidence}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>0</span>
            <span className="font-mono text-foreground text-base">{confidence}%</span>
            <span>100</span>
          </div>
        </div>

        <div className="rounded-xl border border-border/60 bg-muted/30 p-4 min-h-40 space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <TrendingUp className="w-4 h-4 text-success" />
            <span>Profit Momentum</span>
          </div>
          <svg width="100%" height="84" viewBox="0 0 98 44" className="overflow-visible">
            <polyline points={momentumPoints} fill="none" stroke="currentColor" strokeWidth="2.5" className="text-success" />
            <circle cx="10" cy="36" r="1.5" className="fill-success/60" />
            <circle cx="32" cy="34" r="1.5" className="fill-success/70" />
            <circle cx="54" cy="30" r="1.5" className="fill-success/80" />
            <circle cx="76" cy="26" r="1.5" className="fill-success/90" />
            <circle cx="98" cy="22" r="1.5" className="fill-success" />
          </svg>
          <p className="text-xs text-muted-foreground line-clamp-2">{result.trend.insight}</p>
        </div>

        <div className="rounded-xl border border-border/60 bg-muted/30 p-4 min-h-40 space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <TriangleAlert className="w-4 h-4 text-warning" />
            <span>Flag Severity</span>
          </div>
          <div className="space-y-2.5">
            <div className="flex items-center gap-2">
              <span className="w-10 text-xs text-muted-foreground">High</span>
              <div className="h-2.5 flex-1 rounded-full bg-muted/40 overflow-hidden">
                <div className="h-full bg-destructive rounded-full" style={{ width: `${(highSeverity / 3) * 100}%` }} />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-10 text-xs text-muted-foreground">Med</span>
              <div className="h-2.5 flex-1 rounded-full bg-muted/40 overflow-hidden">
                <div className="h-full bg-warning rounded-full" style={{ width: `${(mediumSeverity / 2) * 100}%` }} />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-10 text-xs text-muted-foreground">Low</span>
              <div className="h-2.5 flex-1 rounded-full bg-muted/40 overflow-hidden">
                <div className="h-full bg-primary rounded-full" style={{ width: `${Math.min(lowSeverity, 4) * 25}%` }} />
              </div>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">{flags} total flags detected</p>
        </div>
      </div>
    </div>
  );
}
