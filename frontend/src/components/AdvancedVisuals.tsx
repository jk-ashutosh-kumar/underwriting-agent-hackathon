import type { FinancialData, UnderwritingResult } from '@/types';
import { ActivitySquare, BrainCircuit, ChartNoAxesCombined, Radar, Sparkles } from 'lucide-react';

interface AdvancedVisualsProps {
  result: UnderwritingResult;
  inputData: FinancialData | null;
}

interface CashflowPoint {
  x: number;
  y: number;
  value: number;
  label: string;
}

function buildCashflowSeries(inputData: FinancialData | null): CashflowPoint[] {
  if (!inputData || inputData.transactions.length === 0) {
    return [0, 1, 2, 3, 4, 5].map((i) => ({
      x: i * 20,
      y: 70 - i * 4,
      value: 20000 + i * 9000,
      label: `P${i + 1}`,
    }));
  }

  const tx = inputData.transactions.slice(0, 10);
  let running = 0;
  const points: { value: number; label: string }[] = [];
  for (const t of tx) {
    running += t.type === 'credit' ? t.amount : -t.amount;
    points.push({ value: running, label: t.date.slice(5) });
  }

  const max = Math.max(...points.map((v) => Math.abs(v.value)), 1);
  return points
    .map((point, index) => {
      const x = Math.round((index / Math.max(points.length - 1, 1)) * 100);
      const y = Math.round(40 - (point.value / max) * 26);
      return { x, y: Math.max(6, Math.min(74, y)), value: point.value, label: point.label };
    });
}

function riskContributors(result: UnderwritingResult) {
  const flags = result.audit.flags.length;
  const risk = result.risk_score;
  return [
    { label: 'Fraud Signals', score: Math.min(100, flags * 22 + (risk > 55 ? 16 : 6)) },
    { label: 'Cash Volatility', score: Math.min(100, Math.max(10, Math.abs(result.trend.profit) > 100000 ? 72 : 44)) },
    { label: 'Benchmark Gap', score: result.benchmark.benchmark_result.toLowerCase().includes('high') ? 78 : 36 },
    { label: 'Committee Confidence', score: result.needs_hitl ? 58 : 82 },
  ];
}

export function AdvancedVisuals({ result, inputData }: AdvancedVisualsProps) {
  const series = buildCashflowSeries(inputData);
  const path = series.map((point) => `${point.x},${point.y}`).join(' ');
  const peak = series.reduce((acc, cur) => (cur.value > acc.value ? cur : acc), series[0]);
  const trough = series.reduce((acc, cur) => (cur.value < acc.value ? cur : acc), series[0]);
  const closing = series[series.length - 1]?.value ?? 0;
  const contributors = riskContributors(result);
  const stacked = [
    { label: 'Model risk load', value: Math.min(92, result.risk_score), tone: 'bg-destructive' },
    { label: 'Review touchpoint depth', value: result.needs_hitl ? 52 : 18, tone: 'bg-warning' },
    { label: 'Policy headroom', value: Math.max(12, 100 - result.risk_score), tone: 'bg-success' },
  ];

  return (
    <div className="rounded-2xl border border-border/60 bg-elevated p-6 shadow-sm space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground/80 font-semibold">
          Executive Visualization Layer
        </p>
        <span className="text-xs text-muted-foreground/70 flex items-center gap-1">
          <Sparkles className="w-3.5 h-3.5 text-primary" />
          insight orchestration
        </span>
      </div>

      <div className="grid grid-cols-1 2xl:grid-cols-5 gap-4">
        <div className="2xl:col-span-3 rounded-xl border border-border/60 bg-muted/30 p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
            <ChartNoAxesCombined className="w-4 h-4 text-primary" />
            Cashflow Storyline
          </div>
          <svg width="100%" height="240" viewBox="0 0 100 80" preserveAspectRatio="none">
            <defs>
              <linearGradient id="flowLine" x1="0" x2="1">
                <stop offset="0%" stopColor="#2563eb" />
                <stop offset="100%" stopColor="#06b6d4" />
              </linearGradient>
            </defs>
            <line x1="0" y1="12" x2="100" y2="12" stroke="currentColor" className="text-border/70" strokeDasharray="2 2" />
            <line x1="0" y1="40" x2="100" y2="40" stroke="currentColor" className="text-border/80" strokeDasharray="2 2" />
            <line x1="0" y1="68" x2="100" y2="68" stroke="currentColor" className="text-border/70" strokeDasharray="2 2" />
            <polyline points={path} fill="none" stroke="url(#flowLine)" strokeWidth="2.5" />
            <polyline points={`${path} 100,80 0,80`} fill="url(#flowLine)" fillOpacity="0.08" />
            {series.map((point) => (
              <circle key={`${point.x}-${point.label}`} cx={point.x} cy={point.y} r="1.7" fill="#0ea5e9" />
            ))}
          </svg>
          <div className="grid grid-cols-3 gap-2 text-xs mt-2">
            <div className="rounded-md border border-border/60 bg-background/70 p-2">
              <p className="text-muted-foreground">Peak</p>
              <p className="font-mono text-success">{peak.value.toLocaleString()}</p>
            </div>
            <div className="rounded-md border border-border/60 bg-background/70 p-2">
              <p className="text-muted-foreground">Lowest</p>
              <p className="font-mono text-destructive">{trough.value.toLocaleString()}</p>
            </div>
            <div className="rounded-md border border-border/60 bg-background/70 p-2">
              <p className="text-muted-foreground">Closing</p>
              <p className="font-mono text-primary">{closing.toLocaleString()}</p>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {series.map((point) => (
              <span
                key={`chip-${point.x}-${point.label}`}
                className="text-[10px] px-1.5 py-1 rounded border border-border/60 bg-background/70 text-muted-foreground"
                title={`Net ${point.value.toLocaleString()}`}
              >
                {point.label}: {point.value.toLocaleString()}
              </span>
            ))}
          </div>
          <p className="text-sm text-muted-foreground mt-3">
            Net cash movement generated from parsed transactions to show liquidity direction over time.
          </p>
        </div>

        <div className="2xl:col-span-2 rounded-xl border border-border/60 bg-muted/30 p-4 space-y-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <BrainCircuit className="w-4 h-4 text-accent" />
            Exposure & review load
          </div>
          {stacked.map((item) => (
            <div key={item.label}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-muted-foreground">{item.label}</span>
                <span className="font-mono">{item.value}%</span>
              </div>
              <div className="h-3 rounded-full bg-muted/40 overflow-hidden">
                <div className={`h-full ${item.tone} rounded-full transition-all duration-700`} style={{ width: `${item.value}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="rounded-xl border border-border/60 bg-muted/30 p-4 space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Radar className="w-4 h-4 text-warning" />
            Risk Contributor Breakdown
          </div>
          {contributors.map((item) => (
            <div key={item.label}>
              <div className="flex justify-between text-xs mb-1">
                <span>{item.label}</span>
                <span className="font-mono">{item.score}</span>
              </div>
              <div className="h-2.5 rounded-full bg-muted/40 overflow-hidden">
                <div className="h-full bg-linear-to-r from-warning to-destructive rounded-full" style={{ width: `${item.score}%` }} />
              </div>
            </div>
          ))}
        </div>

        <div className="rounded-xl border border-border/60 bg-muted/30 p-4 space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <ActivitySquare className="w-4 h-4 text-success" />
            Case risk summary
          </div>
          <p className="text-xs text-muted-foreground">
            Quantitative readouts that feed the limit band above. There is no single approve/reject gate here.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-border/60 bg-background/70 p-3">
              <p className="text-xs text-muted-foreground">Cashflow trend</p>
              <p className="text-lg font-semibold mt-1 capitalize">{result.trend.trend}</p>
              {result.trend.growth_signal ? (
                <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-muted-foreground">
                  {result.trend.growth_signal}
                </p>
              ) : null}
            </div>
            <div className="rounded-lg border border-border/60 bg-background/70 p-3">
              <p className="text-xs text-muted-foreground">Limit band midpoint</p>
              <p className="text-lg font-mono mt-1">
                {result.credit_limit != null &&
                Number.isFinite(result.credit_limit.min_limit) &&
                Number.isFinite(result.credit_limit.max_limit)
                  ? ((result.credit_limit.min_limit + result.credit_limit.max_limit) / 2).toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })
                  : '—'}
              </p>
            </div>
            <div className="rounded-lg border border-border/60 bg-background/70 p-3">
              <p className="text-xs text-muted-foreground">Profit signal</p>
              <p className="text-lg font-mono mt-1">{result.trend.profit >= 0 ? '+' : ''}{result.trend.profit.toLocaleString()}</p>
            </div>
            <div className="rounded-lg border border-border/60 bg-background/70 p-3">
              <p className="text-xs text-muted-foreground">Alert flags</p>
              <p className="text-lg font-mono mt-1">{result.audit.flags.length}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
