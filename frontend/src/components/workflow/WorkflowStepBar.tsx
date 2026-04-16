import { cn } from '@/lib/utils';
import { Building2, Upload, Radio, LineChart, Check } from 'lucide-react';

export type WorkflowVisualStep = 'company' | 'upload' | 'extract' | 'analyze' | 'done';

const STEPS: { id: WorkflowVisualStep; label: string; Icon: typeof Building2 }[] = [
  { id: 'company', label: 'Company', Icon: Building2 },
  { id: 'upload', label: 'Upload', Icon: Upload },
  { id: 'extract', label: 'Extract', Icon: Radio },
  { id: 'analyze', label: 'Analyze', Icon: LineChart },
  { id: 'done', label: 'Results', Icon: Check },
];

function stepIndex(id: WorkflowVisualStep) {
  return STEPS.findIndex((s) => s.id === id);
}

interface WorkflowStepBarProps {
  /** Furthest step that is fully satisfied (high water mark). */
  current: WorkflowVisualStep;
  /** Optional pulse on a step that is in progress (e.g. analyzing). */
  busyStep?: WorkflowVisualStep | null;
}

export function WorkflowStepBar({ current, busyStep }: WorkflowStepBarProps) {
  const hi = stepIndex(current);
  return (
    <div className="rounded-xl border border-border/60 bg-elevated/90 p-3">
      <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold mb-3">
        Workflow
      </p>
      <div className="flex items-start justify-between gap-1">
        {STEPS.map((step, i) => {
          const done = i < hi;
          const active = i === hi;
          const busyHere = busyStep === step.id;
          const Icon = step.Icon;
          return (
            <div key={step.id} className="flex flex-1 flex-col items-center gap-1 min-w-0">
              <div
                className={cn(
                  'w-8 h-8 rounded-full border flex items-center justify-center transition-colors shrink-0',
                  done && 'border-success/50 bg-success/15 text-success',
                  active && !done && 'border-primary/50 bg-primary/15 text-primary',
                  !active && !done && 'border-border/60 bg-muted/20 text-muted-foreground/50',
                  busyHere && 'ring-2 ring-primary/30 animate-pulse',
                )}
              >
                <Icon className="w-3.5 h-3.5" />
              </div>
              <span
                className={cn(
                  'text-[9px] text-center leading-tight font-medium truncate w-full',
                  (active || done) && 'text-foreground',
                  !active && !done && 'text-muted-foreground/70',
                )}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
