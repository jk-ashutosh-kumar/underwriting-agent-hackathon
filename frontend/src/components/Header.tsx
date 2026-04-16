import { ShieldCheck, UserPlus, Users } from "lucide-react"
import { ThemeToggle } from "./theme-toggle"

export function Header() {
  return (
    <header className="fixed top-0 right-0 left-0 z-50 flex h-16 items-center border-b border-border/40 bg-card/80 px-6 backdrop-blur-md">
      <div className="flex items-center gap-2.5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-primary/20 bg-primary/10">
          <ShieldCheck className="h-5 w-5 text-primary" />
        </div>
        <div>
          <span className="-mb-1 block text-lg font-bold tracking-tight text-foreground">
            CredServ
          </span>
          <span className="text-[10px] font-medium tracking-[0.2em] text-muted-foreground/50 uppercase">
            Underwriting Agent
          </span>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-4">
        <div className="hidden items-center gap-1.5 rounded-full border border-success/10 bg-success/5 px-3 py-1.5 md:flex">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />
          <span className="text-[11px] font-medium tracking-wider text-success uppercase">
            API Online
          </span>
        </div>

        <div className="mx-2 h-6 w-px bg-border/40" />

        <ThemeToggle />

       
      </div>
    </header>
  )
}
