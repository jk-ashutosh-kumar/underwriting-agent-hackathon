import { ShieldCheck } from 'lucide-react';

export function Header() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-14 flex items-center px-6 border-b border-border/40 bg-background/80 backdrop-blur-md">
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 border border-primary/20">
          <ShieldCheck className="w-4 h-4 text-primary" />
        </div>
        <div>
          <span className="text-sm font-semibold tracking-tight text-foreground">
            AI Credit Underwriting
          </span>
          <span className="ml-2 text-[10px] font-mono uppercase tracking-widest text-muted-foreground/60 border border-border px-1.5 py-0.5 rounded">
            v2.0
          </span>
        </div>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
          API Online
        </span>
      </div>
    </header>
  );
}
