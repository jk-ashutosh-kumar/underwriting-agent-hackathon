import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { AuditResult, TrendResult, BenchmarkResult } from '@/types';
import { ShieldAlert, TrendingUp, BarChart3, AlertTriangle } from 'lucide-react';

function getSourceLabel(mode?: string) {
  if (mode === 'llm') return { text: 'Source: LLM', className: 'bg-primary/10 border-primary/25 text-primary' };
  if (mode === 'deterministic_fallback') {
    return { text: 'Source: Rules (LLM fallback)', className: 'bg-warning/10 border-warning/25 text-warning' };
  }
  return { text: 'Source: Rules', className: 'bg-muted/40 border-border/60 text-muted-foreground' };
}

/* ──────────────────────────── Auditor Card ──────────────────────────── */
interface AuditorCardProps {
  data: AuditResult;
}

export function AuditorCard({ data }: AuditorCardProps) {
  const riskColor =
    data.risk_score < 30 ? 'text-success' : data.risk_score < 60 ? 'text-warning' : 'text-destructive';
  const source = getSourceLabel(data.mode);

  return (
    <Card className="bg-elevated border-border/60 hover:border-primary/30 transition-colors">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-destructive/10 border border-destructive/20 flex items-center justify-center">
              <ShieldAlert className="w-4 h-4 text-destructive" />
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Fraud Detection</p>
              <p className="text-sm font-semibold text-foreground">Auditor Agent</p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Badge className={cn('text-[10px] border', source.className)}>{source.text}</Badge>
            <span className={cn('font-mono text-2xl font-bold', riskColor)}>{data.risk_score}</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground leading-relaxed">{data.explanation}</p>
        {data.flags.length > 0 ? (
          <div className="space-y-1.5">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60">Flags</p>
            {data.flags.map((flag, i) => (
              <div key={i} className="flex items-start gap-2 p-2 rounded-md bg-destructive/5 border border-destructive/15">
                <AlertTriangle className="w-3 h-3 text-destructive shrink-0 mt-0.5" />
                <span className="text-xs text-destructive/80">{flag}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center gap-2 p-2 rounded-md bg-success/5 border border-success/15">
            <span className="w-1.5 h-1.5 rounded-full bg-success" />
            <span className="text-xs text-success/80">No flags detected</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ──────────────────────────── Trend Card ──────────────────────────── */
interface TrendCardProps {
  data: TrendResult;
}

const TREND_STYLE = {
  growing: { color: 'text-success', bg: 'bg-success/10 border-success/20', badge: 'Growing ↑' },
  stable: { color: 'text-primary', bg: 'bg-primary/10 border-primary/20', badge: 'Stable →' },
  shrinking: { color: 'text-destructive', bg: 'bg-destructive/10 border-destructive/20', badge: 'Shrinking ↓' },
};

export function TrendCard({ data }: TrendCardProps) {
  const style = TREND_STYLE[data.trend];
  const profitPositive = data.profit >= 0;
  const source = getSourceLabel(data.mode);

  return (
    <Card className="bg-elevated border-border/60 hover:border-primary/30 transition-colors">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-primary" />
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Growth Analyst</p>
              <p className="text-sm font-semibold text-foreground">Trend Agent</p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Badge className={cn('text-[10px] border', source.className)}>{source.text}</Badge>
            <Badge className={cn('text-[10px] border', style.bg, style.color)}>
              {style.badge}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <div className="p-2.5 rounded-md bg-muted/30 border border-border/40">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60">Profit</p>
            <p className={cn('text-sm font-mono font-bold mt-0.5', profitPositive ? 'text-success' : 'text-destructive')}>
              {profitPositive ? '+' : ''}{data.profit.toLocaleString()}
            </p>
          </div>
          <div className="p-2.5 rounded-md bg-muted/30 border border-border/40">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60">Trend</p>
            <p className={cn('text-sm font-semibold mt-0.5 capitalize', style.color)}>{data.trend}</p>
          </div>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">{data.insight}</p>
      </CardContent>
    </Card>
  );
}

/* ──────────────────────────── Benchmark Card ──────────────────────────── */
interface BenchmarkCardProps {
  data: BenchmarkResult;
}

export function BenchmarkCard({ data }: BenchmarkCardProps) {
  const isHighRisk = data.benchmark_result.toLowerCase().includes('high');
  const source = getSourceLabel(data.mode);

  return (
    <Card className="bg-elevated border-border/60 hover:border-primary/30 transition-colors">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
              <BarChart3 className="w-4 h-4 text-accent" />
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Portfolio Manager</p>
              <p className="text-sm font-semibold text-foreground">Benchmark Agent</p>
            </div>
          </div>
          <Badge className={cn('text-[10px] border', source.className)}>{source.text}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className={cn(
          'p-2.5 rounded-md border text-xs font-medium',
          isHighRisk
            ? 'bg-destructive/5 border-destructive/20 text-destructive/80'
            : 'bg-success/5 border-success/20 text-success/80',
        )}>
          {data.benchmark_result}
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">{data.comparison_insight}</p>
      </CardContent>
    </Card>
  );
}
