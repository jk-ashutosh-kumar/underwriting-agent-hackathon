import { useMemo } from 'react';
import type { UnderwritingResult } from '@/types';
import { cn } from '@/lib/utils';
import { Activity, ShieldCheck, TrendingUp, TriangleAlert } from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
  Label,
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

/* ────────────────────────────────────────────────────────────────────────── */

function RiskDonut({ score }: { score: number }) {
  const data = useMemo(() => [
    { name: 'Risk', value: score },
    { name: 'Safe', value: 100 - score },
  ], [score]);

  const color = score < 30 ? COLORS.success : score < 60 ? COLORS.warning : COLORS.destructive;

  return (
    <div className="h-32 w-full relative">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={38}
            outerRadius={50}
            startAngle={90}
            endAngle={-270}
            dataKey="value"
            stroke="none"
          >
            <Cell fill={color} />
            <Cell fill="var(--muted)" opacity={0.2} />
            {/* <Label
              value={`${score}%`}
              position="center"
              content={({ viewBox }) => {
                const { cx, cy } = viewBox as { cx: number; cy: number };
                return (
                  <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle">
                    <tspan x={cx} y={cy} className="text-xl font-mono font-bold">
                      {score}%
                    </tspan>
                  </text>
                );
              }}
            /> */}
          </Pie>
          <Tooltip 
            contentStyle={{ backgroundColor: 'var(--card)', borderColor: 'var(--border)', borderRadius: '8px', fontSize: '10px' }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function momentumData(profit: number, trend: string) {
  const base = [3000, 4500, 4200, 5800, profit];
  return base.map((v, i) => ({ name: `T-${4-i}`, value: v }));
}

function MomentumLine({ profit, trend }: { profit: number; trend: string }) {
  const data = useMemo(() => momentumData(profit, trend), [profit, trend]);
  
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
<<<<<<< Updated upstream
  const risk = Math.max(0, Math.min(100, result.risk_score));
  const visibleRisk = risk === 0 ? 1.8 : risk;
  const confidence = getDecisionConfidence(result.decision_status);
  const flags = result.audit.flags.length;
  const highSeverity = Math.min(flags, 3);
  const mediumSeverity = Math.max(0, Math.min(flags - highSeverity, 2));
  const lowSeverity = Math.max(0, flags - highSeverity - mediumSeverity);
  const momentumPoints = buildMomentumPoints(result.trend.profit, result.trend.trend);
=======
  const confidence = result.decision_status === 'APPROVED' ? 86 : result.decision_status === 'REJECTED' ? 12 : 62;
>>>>>>> Stashed changes

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full">
      {/* Risk Composition */}
      <div className="group rounded-2xl border border-border/40 bg-card p-6 shadow-sm hover:shadow-lg hover:scale-[1.02] transition-all duration-300 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/5">
              <ShieldCheck className="w-4 h-4 text-primary" />
            </div>
            <span className="text-sm font-semibold text-foreground">Risk Composition</span>
          </div>
          <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">Live Analysis</span>
        </div>
        <RiskDonut score={result.risk_score} />
        <p className="text-xs text-muted-foreground leading-relaxed">
          Aggregated risk factor based on {result.audit.flags.length} audit checkpoints.
        </p>
      </div>

<<<<<<< Updated upstream
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border/60 bg-muted/30 p-4 min-h-40 space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <ShieldCheck className="w-4 h-4 text-primary" />
            <span>Risk Composition</span>
          </div>
          <div className="flex items-center gap-4">
            <svg width="78" height="78" viewBox="0 0 42 42" className="-rotate-90">
              <circle cx="21" cy="21" r="15.915" fill="none" stroke="currentColor" strokeWidth="4.2" className="text-slate-300" />
              <circle
                cx="21"
                cy="21"
                r="15.915"
                fill="none"
                stroke="currentColor"
                strokeWidth="4.2"
                strokeDasharray={`${visibleRisk} ${Math.max(100 - visibleRisk, 0.1)}`}
                className={cn(risk < 30 ? 'text-success' : risk < 60 ? 'text-warning' : 'text-destructive')}
              />
            </svg>
            <div>
              <p className="text-xl font-mono font-bold">{risk}%</p>
              <p className="text-xs text-muted-foreground mt-1">{getRiskBand(risk)} exposure</p>
              <p className="text-[10px] text-muted-foreground/70 mt-0.5">Lower is better</p>
=======
      {/* Decision Confidence */}
      <div className="group rounded-2xl border border-border/40 bg-card p-6 shadow-sm hover:shadow-lg hover:scale-[1.02] transition-all duration-300 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-accent/5">
              <Activity className="w-4 h-4 text-accent" />
>>>>>>> Stashed changes
            </div>
            <span className="text-sm font-semibold text-foreground">Decision Confidence</span>
          </div>
        </div>
        <div className="flex-1 flex flex-col justify-center gap-4">
          <div className="relative h-4 w-full rounded-full bg-muted/30 overflow-hidden">
            <div 
              className="absolute inset-y-0 left-0 bg-linear-to-r from-primary to-accent transition-all duration-1000 ease-out rounded-full"
              style={{ width: `${confidence}%` }}
            />
          </div>
          <div className="flex justify-between items-end">
            <div>
              <p className="text-3xl font-mono font-bold text-foreground">{confidence}%</p>
              <p className="text-[10px] text-muted-foreground uppercase tracking-widest mt-1">Confidence Score</p>
            </div>
            <div className="text-right">
              <p className="text-xs font-semibold text-foreground">{result.decision_status}</p>
              <p className="text-[10px] text-muted-foreground uppercase tracking-widest mt-1">Current Status</p>
            </div>
          </div>
        </div>
      </div>

      {/* Profit Momentum */}
      <div className="group rounded-2xl border border-border/40 bg-card p-6 shadow-sm hover:shadow-lg hover:scale-[1.02] transition-all duration-300 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-success/5">
              <TrendingUp className="w-4 h-4 text-success" />
            </div>
            <span className="text-sm font-semibold text-foreground">Profit Momentum</span>
          </div>
        </div>
        <MomentumLine profit={result.trend.profit} trend={result.trend.trend} />
        <p className="text-xs text-muted-foreground line-clamp-2">
          {result.trend.insight}
        </p>
      </div>

      {/* Flag Severity */}
      <div className="group rounded-2xl border border-border/40 bg-card p-6 shadow-sm hover:shadow-lg hover:scale-[1.02] transition-all duration-300 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-warning/5">
              <TriangleAlert className="w-4 h-4 text-warning" />
            </div>
            <span className="text-sm font-semibold text-foreground">Flag Severity</span>
          </div>
<<<<<<< Updated upstream
          <div className="space-y-2.5">
            <div className="flex items-center gap-2">
              <span className="w-10 text-xs text-muted-foreground">High</span>
              <div className="h-2.5 flex-1 rounded-full bg-muted/40 overflow-hidden">
                <div className="h-full bg-destructive rounded-full min-w-[2px]" style={{ width: `${(highSeverity / 3) * 100}%` }} />
              </div>
              <span className="w-7 text-right text-[10px] text-muted-foreground">{highSeverity}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-10 text-xs text-muted-foreground">Med</span>
              <div className="h-2.5 flex-1 rounded-full bg-muted/40 overflow-hidden">
                <div className="h-full bg-warning rounded-full min-w-[2px]" style={{ width: `${(mediumSeverity / 2) * 100}%` }} />
              </div>
              <span className="w-7 text-right text-[10px] text-muted-foreground">{mediumSeverity}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-10 text-xs text-muted-foreground">Low</span>
              <div className="h-2.5 flex-1 rounded-full bg-muted/40 overflow-hidden">
                <div className="h-full bg-primary rounded-full min-w-[2px]" style={{ width: `${Math.min(lowSeverity, 4) * 25}%` }} />
              </div>
              <span className="w-7 text-right text-[10px] text-muted-foreground">{lowSeverity}</span>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">{flags} total flags detected</p>
=======
>>>>>>> Stashed changes
        </div>
        <SeverityBars flags={result.audit.flags} />
        <p className="text-xs text-muted-foreground">
          Detailed breakdown of {result.audit.flags.length} potential risk flags.
        </p>
      </div>
    </div>
  );
}
