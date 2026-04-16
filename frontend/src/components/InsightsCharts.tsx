import { useMemo } from 'react';
import type { UnderwritingResult } from '@/types';
import { Scale, TrendingUp, TriangleAlert, Users } from 'lucide-react';
import { RiskGauge } from './RiskGauge';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Cell,
} from 'recharts';

interface InsightsChartsProps {
  result: UnderwritingResult;
}

const COLORS = {
  success: 'var(--success)',
  warning: 'var(--warning)',
  destructive: 'var(--destructive)',
  primary: 'var(--primary)',
  accent: 'var(--accent)',
  muted: 'var(--muted-foreground)',
};

function momentumData(profit: number) {
  const base = [3000, 4500, 4200, 5800, profit];
  return base.map((v, i) => ({ name: `T-${4 - i}`, value: v }));
}

function MomentumLine({ profit }: { profit: number }) {
  const data = useMemo(() => momentumData(profit), [profit]);

  return (
    <div className="h-32 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Tooltip
            contentStyle={{ backgroundColor: 'var(--card)', borderColor: 'var(--border)', borderRadius: '8px', fontSize: '10px' }}
            itemStyle={{ color: 'var(--success)' }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="var(--success)"
            strokeWidth={3}
            dot={{ r: 3, fill: 'var(--success)', strokeWidth: 0 }}
            activeDot={{ r: 5, strokeWidth: 0 }}
            animationDuration={1500}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function SeverityBars({ flags }: { flags: string[] }) {
  const total = flags.length;
  const high = Math.min(total, 3);
  const med = Math.max(0, Math.min(total - high, 2));
  const low = Math.max(0, total - high - med);

  const data = [
    { name: 'High', value: high, color: COLORS.destructive },
    { name: 'Med', value: med, color: COLORS.warning },
    { name: 'Low', value: low, color: COLORS.primary },
  ];

  return (
    <div className="h-32 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: -20, right: 10 }}>
          <XAxis type="number" hide domain={[0, 4]} />
          <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }} />
          <Tooltip
            cursor={{ fill: 'transparent' }}
            contentStyle={{ backgroundColor: 'var(--card)', borderColor: 'var(--border)', borderRadius: '8px', fontSize: '10px' }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={12}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function InsightsCharts({ result }: InsightsChartsProps) {
  const chairConfidence = Math.max(
    0,
    Math.min(100, Number(result.committee_chair?.confidence ?? 0)),
  );

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full">
      <div className="group rounded-2xl border border-border/40 bg-card p-6 shadow-sm hover:shadow-lg hover:scale-[1.02] transition-all duration-300 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/5">
              <Scale className="w-4 h-4 text-primary" />
            </div>
            <span className="text-sm font-semibold text-foreground">Risk snapshot</span>
          </div>
          <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">0–100</span>
        </div>
        <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
          <div className="flex shrink-0 justify-center">
            <RiskGauge score={result.risk_score} />
          </div>
          <div className="text-center sm:text-right">
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Committee risk score</p>
            <p className="font-mono text-3xl font-semibold tabular-nums tracking-tight text-foreground">
              {result.risk_score}
            </p>
            <p className="text-[10px] text-muted-foreground">Lower is better</p>
          </div>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Model readout from the auditor and flow; not a consumer credit score.
        </p>
      </div>

      <div className="group rounded-2xl border border-border/40 bg-card p-6 shadow-sm hover:shadow-lg hover:scale-[1.02] transition-all duration-300 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-accent/5">
              <Users className="w-4 h-4 text-accent" />
            </div>
            <span className="text-sm font-semibold text-foreground">Chair synthesis confidence</span>
          </div>
        </div>
        <div className="flex-1 flex flex-col justify-center gap-4">
          <div className="relative h-4 w-full rounded-full bg-muted/30 overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 bg-linear-to-r from-primary to-accent transition-all duration-1000 ease-out rounded-full"
              style={{ width: `${chairConfidence}%` }}
            />
          </div>
          <div>
            <p className="text-3xl font-mono font-bold text-foreground">{chairConfidence}%</p>
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest mt-1">
              Committee chair output
            </p>
            {/* <p className="mt-2 text-xs text-muted-foreground">
              Routing outcome is shown elsewhere; this bar is only how sure the chair is about its narrative.
            </p> */}
          </div>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          This is the chair agent’s self-reported confidence in its written synthesis. It is not the model risk
          score on the left, and it is not an approval probability.
        </p>
      </div>

      <div className="group rounded-2xl border border-border/40 bg-card p-6 shadow-sm hover:shadow-lg hover:scale-[1.02] transition-all duration-300 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-success/5">
              <TrendingUp className="w-4 h-4 text-success" />
            </div>
            <span className="text-sm font-semibold text-foreground">Profit Momentum</span>
          </div>
        </div>
        <MomentumLine profit={result.trend.profit} />
        <p className="text-xs text-muted-foreground line-clamp-2">
          {result.trend.insight}
        </p>
      </div>

      <div className="group rounded-2xl border border-border/40 bg-card p-6 shadow-sm hover:shadow-lg hover:scale-[1.02] transition-all duration-300 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-warning/5">
              <TriangleAlert className="w-4 h-4 text-warning" />
            </div>
            <span className="text-sm font-semibold text-foreground">Flag Severity</span>
          </div>
        </div>
        <SeverityBars flags={result.audit.flags} />
        <p className="text-xs text-muted-foreground">
          Detailed breakdown of {result.audit.flags.length} potential risk flags.
        </p>
      </div>
    </div>
  );
}
