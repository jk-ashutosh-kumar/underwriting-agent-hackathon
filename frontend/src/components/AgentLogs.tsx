import { ScrollArea } from "@/components/ui/scroll-area"
import { Terminal } from "lucide-react"
import { cn } from "@/lib/utils"

interface AgentLogsProps {
  logs: string[]
}

export function AgentLogs({ logs }: AgentLogsProps) {
  if (logs.length === 0) return null

  return (
    <div className="overflow-hidden rounded-xl border border-border/40 bg-primary/[0.03] dark:bg-[#0a1a16]">
      <div className="flex items-center gap-2 border-b border-border/40 bg-primary/[0.05] dark:bg-[#0d211c] px-4 py-2.5">
        <Terminal className="h-4 w-4 text-primary/70" />
        <span className="text-[10px] font-bold tracking-[0.15em] text-foreground/80 uppercase">
          Agent Logs
        </span>
        <span className="ml-auto font-mono text-[10px] text-muted-foreground/50">
          {logs.length} entries
        </span>
      </div>
      <ScrollArea className="h-48">
        <div className="flex flex-col font-mono text-[11px]">
          {logs.map((log, i) => (
            <div
              key={i}
              className={cn(
                "flex gap-4 px-4 py-3 hover:bg-primary/[0.08] dark:hover:bg-[#112a24] transition-colors duration-200 cursor-pointer group",
                i !== logs.length - 1 && "border-b border-border/60"
              )}
            >
              <span className="shrink-0 text-muted-foreground/40 font-medium select-none group-hover:text-primary transition-colors">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="text-foreground/90 group-hover:text-foreground transition-colors break-all leading-relaxed">
                {log}
              </span>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
