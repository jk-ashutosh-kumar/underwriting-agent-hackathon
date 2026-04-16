import { cn } from '@/lib/utils';
import { CheckCircle2, Loader2, MinusCircle } from 'lucide-react';

/** LangGraph-style stages (matches backend stream order). */
export const PIPELINE_STEPS = [
  { id: 'ingesting', label: 'Ingest' },
  { id: 'analysis', label: 'Committee' },
  { id: 'router', label: 'Router' },
  { id: 'hitl', label: 'HITL' },
  { id: 'resume', label: 'Resume' },
  { id: 'deciding', label: 'Decision' },
  { id: 'checkpoint', label: 'Checkpoint' },
] as const;

export type PipelineStepId = (typeof PIPELINE_STEPS)[number]['id'];

type StepStatus = 'done' | 'active' | 'pending' | 'skipped';

function stepStatus(
  stepIndex: number,
  activeIndex: number,
  done: boolean,
  skippedIds: Set<string>,
  stepId: string,
): StepStatus {
  if (skippedIds.has(stepId)) return 'skipped';
  if (done) return 'done';
  if (stepIndex < activeIndex) return 'done';
  if (stepIndex === activeIndex) return 'active';
  return 'pending';
}

export interface PipelineFlowProps {
  /** Index of the step currently executing (0–6). Use 7 only when ``done`` is true. */
  activeIndex: number;
  skippedStepIds?: string[];
  done?: boolean;
  progressLabel?: string | null;
}

export function PipelineFlow({
  activeIndex,
  skippedStepIds = [],
  done = false,
  progressLabel,
}: PipelineFlowProps) {
  if (activeIndex < 0) return null;

  const skipped = new Set(skippedStepIds);

  return (
    <div className="w-full space-y-2">
      <div className="flex items-center justify-center gap-0 w-full py-2 flex-wrap">
        {PIPELINE_STEPS.map((step, idx) => {
          const status = stepStatus(idx, activeIndex, done, skipped, step.id);
          return (
            <div key={step.id} className="flex items-center">
              <div className="flex flex-col items-center gap-1 min-w-[56px]">
                <div
                  className={cn(
                    'flex items-center justify-center w-7 h-7 rounded-full border text-xs font-mono transition-all duration-500',
                    status === 'done' && 'bg-success/20 border-success text-success',
                    status === 'active' && 'bg-primary/20 border-primary text-primary animate-pulse',
                    status === 'pending' && 'bg-muted border-border text-muted-foreground',
                    status === 'skipped' && 'bg-muted/50 border-border/60 text-muted-foreground',
                  )}
                >
                  {status === 'done' ? (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  ) : status === 'skipped' ? (
                    <MinusCircle className="w-3.5 h-3.5" />
                  ) : status === 'active' ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <span>{idx + 1}</span>
                  )}
                </div>
                <span
                  className={cn(
                    'text-[10px] uppercase tracking-widest font-medium text-center max-w-[72px] leading-tight',
                    status === 'done' && 'text-success',
                    status === 'active' && 'text-primary',
                    status === 'pending' && 'text-muted-foreground/40',
                    status === 'skipped' && 'text-muted-foreground/60 line-through',
                  )}
                >
                  {step.label}
                </span>
              </div>
              {idx < PIPELINE_STEPS.length - 1 && (
                <div
                  className={cn(
                    'w-8 sm:w-10 h-px mx-0.5 mt-[-18px] transition-all duration-700 shrink-0',
                    stepStatus(idx + 1, activeIndex, done, skipped, PIPELINE_STEPS[idx + 1].id) !== 'pending' || done
                      ? 'bg-primary/40'
                      : 'bg-border',
                  )}
                />
              )}
            </div>
          );
        })}
      </div>
      {progressLabel && (
        <p className="text-center text-[11px] text-muted-foreground font-mono px-2 truncate" title={progressLabel}>
          {progressLabel}
        </p>
      )}
    </div>
  );
}
