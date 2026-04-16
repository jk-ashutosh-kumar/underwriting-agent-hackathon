import { ShieldCheck } from 'lucide-react';

export function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-5 text-center p-12">
      <div className="relative">
        <div className="w-20 h-20 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center">
          <ShieldCheck className="w-10 h-10 text-primary/60" />
        </div>
        <div className="absolute inset-0 rounded-2xl bg-primary/5 blur-xl" />
      </div>
      <div className="space-y-2 max-w-xs">
        <h2 className="text-lg font-semibold text-foreground">Ready to Underwrite</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Select a company, upload financial documents, and the platform will parse, validate, and
          run analysis automatically through the multi-agent credit committee.
        </p>
      </div>
      <div className="flex flex-col items-start gap-2 text-left bg-muted/10 border border-border/40 rounded-xl p-4 max-w-xs w-full">
        <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-semibold">Pipeline</p>
        {['Fraud Detection (Auditor)', 'Growth Analysis (Trend)', 'Portfolio Comparison (Benchmark)', 'Final Decision'].map((step, i) => (
          <div key={step} className="flex items-center gap-2">
            <span className="w-5 h-5 rounded-full border border-border text-[10px] font-mono flex items-center justify-center text-muted-foreground/60 shrink-0">
              {i + 1}
            </span>
            <span className="text-xs text-muted-foreground">{step}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
