import { ScrollArea } from '@/components/ui/scroll-area';
import { Terminal } from 'lucide-react';

interface AgentLogsProps {
  logs: string[];
}

export function AgentLogs({ logs }: AgentLogsProps) {
  if (logs.length === 0) return null;

  return (
    <div className="rounded-xl border border-border/60 bg-[#080C18] overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border/40 bg-muted/10">
        <Terminal className="w-3.5 h-3.5 text-primary" />
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">
          Agent Logs
        </span>
        <span className="ml-auto text-[10px] font-mono text-muted-foreground/40">{logs.length} entries</span>
      </div>
      <ScrollArea className="h-48">
        <div className="p-4 space-y-1.5 font-mono text-xs">
          {logs.map((log, i) => (
            <div key={i} className="flex gap-3 leading-relaxed">
              <span className="text-primary/30 shrink-0 select-none">{String(i + 1).padStart(2, '0')}</span>
              <span className="text-muted-foreground/80">{log}</span>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
