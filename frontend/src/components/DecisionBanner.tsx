import { cn } from '@/lib/utils';
import type { DecisionStatus } from '@/types';
import { CheckCircle2, XCircle, AlertOctagon, Clock } from 'lucide-react';

interface DecisionBannerProps {
  status: DecisionStatus;
  finalSummary: string;
}

const DECISION_CONFIG: Record<
  DecisionStatus,
  { icon: React.ElementType; label: string; colorClass: string; glowColor: string }
> = {
  APPROVED: {
    icon: CheckCircle2,
    label: 'Approved',
    colorClass: 'text-success border-success/30 bg-success/10',
    glowColor: '#10B981',
  },
  REJECTED: {
    icon: XCircle,
    label: 'Rejected',
    colorClass: 'text-destructive border-destructive/30 bg-destructive/10',
    glowColor: '#EF4444',
  },
  FLAGGED: {
    icon: AlertOctagon,
    label: 'Flagged — Human Review',
    colorClass: 'text-warning border-warning/30 bg-warning/10',
    glowColor: '#F59E0B',
  },
  PENDING: {
    icon: Clock,
    label: 'Pending',
    colorClass: 'text-muted-foreground border-border bg-muted/30',
    glowColor: '#64748B',
  },
};

export function DecisionBanner({ status, finalSummary }: DecisionBannerProps) {
  const config = DECISION_CONFIG[status];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        'rounded-xl border-2 p-5 flex flex-col gap-3 transition-all duration-500',
        config.colorClass,
      )}
      style={{ boxShadow: `0 0 30px ${config.glowColor}20` }}
    >
      <div className="flex items-center gap-3">
        <Icon className="w-7 h-7 shrink-0" />
        <div>
          <p className="text-[10px] uppercase tracking-widest font-semibold opacity-70">
            Underwriting Decision
          </p>
          <p className="text-2xl font-bold tracking-tight">{config.label}</p>
        </div>
      </div>
      {finalSummary && (
        <p className="text-xs leading-relaxed opacity-80 border-t border-current/10 pt-3">
          {finalSummary}
        </p>
      )}
    </div>
  );
}
