import { cn } from '@/lib/utils';
import { CheckCircle2, Loader2 } from 'lucide-react';

const PIPELINE_STEPS = [
  { id: 'ingesting', label: 'Ingest' },
  { id: 'auditing', label: 'Audit' },
  { id: 'trending', label: 'Trend' },
  { id: 'benchmarking', label: 'Benchmark' },
  { id: 'deciding', label: 'Decision' },
] as const;

type Step = 'idle' | 'ingesting' | 'auditing' | 'trending' | 'benchmarking' | 'deciding' | 'done';

const STEP_ORDER = ['ingesting', 'auditing', 'trending', 'benchmarking', 'deciding', 'done'];

function getStepStatus(stepId: string, currentStep: Step): 'done' | 'active' | 'pending' {
  if (currentStep === 'idle') return 'pending';
  const currentIdx = STEP_ORDER.indexOf(currentStep);
  const stepIdx = STEP_ORDER.indexOf(stepId);
  if (currentStep === 'done') return 'done';
  if (stepIdx < currentIdx) return 'done';
  if (stepIdx === currentIdx) return 'active';
  return 'pending';
}

interface PipelineFlowProps {
  currentStep: Step;
}

export function PipelineFlow({ currentStep }: PipelineFlowProps) {
  if (currentStep === 'idle') return null;

  return (
    <div className="flex items-center justify-center gap-0 w-full py-2">
      {PIPELINE_STEPS.map((step, idx) => {
        const status = getStepStatus(step.id, currentStep);
        return (
          <div key={step.id} className="flex items-center">
            <div className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  'flex items-center justify-center w-7 h-7 rounded-full border text-xs font-mono transition-all duration-500',
                  status === 'done' && 'bg-success/20 border-success text-success',
                  status === 'active' && 'bg-primary/20 border-primary text-primary animate-pulse',
                  status === 'pending' && 'bg-muted border-border text-muted-foreground',
                )}
              >
                {status === 'done' ? (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                ) : status === 'active' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <span>{idx + 1}</span>
                )}
              </div>
              <span
                className={cn(
                  'text-[10px] uppercase tracking-widest font-medium',
                  status === 'done' && 'text-success',
                  status === 'active' && 'text-primary',
                  status === 'pending' && 'text-muted-foreground/40',
                )}
              >
                {step.label}
              </span>
            </div>
            {idx < PIPELINE_STEPS.length - 1 && (
              <div
                className={cn(
                  'w-12 h-px mx-1 mt-[-14px] transition-all duration-700',
                  getStepStatus(PIPELINE_STEPS[idx + 1].id, currentStep) !== 'pending' ||
                    currentStep === 'done'
                    ? 'bg-primary/40'
                    : 'bg-border',
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
