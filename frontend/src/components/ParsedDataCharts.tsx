import type { FinancialData } from '@/types';
import { ArrowDownRight, ArrowUpRight, CandlestickChart, Wallet } from 'lucide-react';

interface ParsedDataChartsProps {
  data: FinancialData;
}

function buildSeries(data: FinancialData) {
  const dayMap = new Map<string, { credit: number; debit: number }>();

  for (const tx of data.transactions) {
    const key = tx.date;
    const current = dayMap.get(key) ?? { credit: 0, debit: 0 };
    if (tx.type === 'credit') current.credit += tx.amount;
    else current.debit += tx.amount;
    dayMap.set(key, current);
  }

  return Array.from(dayMap.entries())
    .map(([date, values]) => ({ date, ...values, net: values.credit - values.debit }))
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-7);
}

export function ParsedDataCharts({ data }: ParsedDataChartsProps) {
  const inflow = Math.max(1, data.total_inflow);
  const outflow = Math.max(0, data.total_outflow);
  const total = inflow + outflow;
  const inflowPct = Math.round((inflow / total) * 100);
  const series = buildSeries(data);
  const maxAbsNet = Math.max(1, ...series.map((s) => Math.abs(s.net)));

  return (
    <div className="rounded-2xl border border-border/60 bg-elevated p-6 shadow-sm space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground/80 font-semibold">
          Parsed Statement Analytics
        </p>
        <span className="text-xs text-muted-foreground/70">{data.transactions.length} transactions parsed</span>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border/60 bg-muted/30 p-4 xl:col-span-1">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-3">
            <Wallet className="w-4 h-4 text-primary" />
            Inflow vs Outflow
          </div>
          <div className="h-3 rounded-full bg-muted/40 overflow-hidden">
            <div className="h-full bg-linear-to-r from-success to-accent" style={{ width: `${inflowPct}%` }} />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-md border border-success/30 bg-success/10 p-2.5">
              <p className="text-muted-foreground">Inflow</p>
              <p className="font-mono text-success text-sm">+{data.total_inflow.toLocaleString()}</p>
            </div>
            <div className="rounded-md border border-destructive/30 bg-destructive/10 p-2.5">
              <p className="text-muted-foreground">Outflow</p>
              <p className="font-mono text-destructive text-sm">-{data.total_outflow.toLocaleString()}</p>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border/60 bg-muted/30 p-4 xl:col-span-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
            <CandlestickChart className="w-4 h-4 text-accent" />
            Net Daily Movement (last 7 days)
          </div>
          <div className="h-52 flex items-end gap-3">
            {series.map((point) => {
              const positive = point.net >= 0;
              const height = Math.max(16, Math.round((Math.abs(point.net) / maxAbsNet) * 170));
              return (
                <div key={point.date} className="flex-1 flex flex-col items-center justify-end gap-2">
                  <div
                    className={positive ? 'w-full rounded-t-md bg-success/80' : 'w-full rounded-t-md bg-destructive/80'}
                    style={{ height: `${height}px` }}
                    title={`${point.date}: ${point.net.toLocaleString()}`}
                  />
                  <span className="text-xs text-muted-foreground/80">
                    {point.date.slice(5)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg border border-success/20 bg-success/10 p-3 text-sm flex items-center gap-2">
          <ArrowUpRight className="w-4 h-4 text-success" />
          <span className="text-muted-foreground">Credit Txns:</span>
          <span className="font-mono text-success ml-auto text-base">{data.transactions.filter((t) => t.type === 'credit').length}</span>
        </div>
        <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm flex items-center gap-2">
          <ArrowDownRight className="w-4 h-4 text-destructive" />
          <span className="text-muted-foreground">Debit Txns:</span>
          <span className="font-mono text-destructive ml-auto text-base">{data.transactions.filter((t) => t.type === 'debit').length}</span>
        </div>
      </div>
    </div>
  );
}
