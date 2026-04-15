import { cn } from '@/lib/utils';
import { Binary, Check, FileSearch, FileText, ScanSearch, ShieldCheck } from 'lucide-react';

const WORKFLOW_STEPS = [
  { label: 'Document pre-processing', icon: FileText },
  { label: 'Document classification', icon: ScanSearch },
  { label: 'Data extraction', icon: Binary },
  { label: 'Data validation', icon: ShieldCheck },
  { label: 'Data analysis', icon: FileSearch },
  { label: 'Integration & human review', icon: Check },
] as const;

interface DocumentParseWorkflowProps {
  activeStep: number;
  active: boolean;
  complete: boolean;
}

function getStepState(index: number, activeStep: number, active: boolean, complete: boolean) {
  if (complete) return 'done';
  if (!active) return 'pending';
  if (index < activeStep) return 'done';
  if (index === activeStep) return 'active';
  return 'pending';
}

export function DocumentParseWorkflow({ activeStep, active, complete }: DocumentParseWorkflowProps) {
  if (!active && !complete) return null;

  return (
    <div className="rounded-xl border border-border/60 bg-elevated/80 p-3 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-[10px] uppercase tracking-widest text-muted-foreground/70 font-semibold">
          Intelligent Parsing Workflow
        </p>
        <span className="text-[10px] text-muted-foreground/60">
          {complete ? 'Completed' : `Step ${Math.min(activeStep + 1, WORKFLOW_STEPS.length)} / ${WORKFLOW_STEPS.length}`}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {WORKFLOW_STEPS.map((step, index) => {
          const state = getStepState(index, activeStep, active, complete);
          const Icon = step.icon;
          return (
            <div
              key={step.label}
              className={cn(
                'rounded-lg border p-2.5 transition-all duration-500',
                state === 'done' && 'border-success/30 bg-success/10',
                state === 'active' && 'border-primary/40 bg-primary/10 shadow-[0_0_0_1px_rgba(59,130,246,0.25)]',
                state === 'pending' && 'border-border/50 bg-muted/15',
              )}
            >
              <div className="flex items-start gap-2">
                <div
                  className={cn(
                    'w-6 h-6 rounded-md border flex items-center justify-center',
                    state === 'done' && 'border-success/40 text-success',
                    state === 'active' && 'border-primary/50 text-primary animate-pulse',
                    state === 'pending' && 'border-border text-muted-foreground/50',
                  )}
                >
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] leading-snug text-foreground/90">{step.label}</p>
                  <p className="text-[10px] text-muted-foreground/60 mt-1">
                    {state === 'done' ? 'done' : state === 'active' ? 'in progress...' : 'queued'}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
