import { cn } from '@/lib/utils';

interface RiskGaugeProps {
  score: number; // 0–100
}

function getRiskColor(score: number): string {
  if (score < 30) return '#10B981'; // green
  if (score < 60) return '#F59E0B'; // amber
  return '#EF4444'; // red
}

function getRiskLabel(score: number): string {
  if (score < 30) return 'Low Risk';
  if (score < 60) return 'Medium Risk';
  return 'High Risk';
}

export function RiskGauge({ score }: RiskGaugeProps) {
  const color = getRiskColor(score);
  const label = getRiskLabel(score);

  // SVG arc gauge
  const radius = 54;
  const cx = 70;
  const cy = 70;
  const startAngle = -210;
  const endAngle = 30;
  const totalAngle = endAngle - startAngle; // 240 degrees
  const fillAngle = (score / 100) * totalAngle;

  function polarToCartesian(angle: number) {
    const rad = ((angle - 90) * Math.PI) / 180;
    return {
      x: cx + radius * Math.cos(rad),
      y: cy + radius * Math.sin(rad),
    };
  }

  function describeArc(start: number, end: number) {
    const s = polarToCartesian(start);
    const e = polarToCartesian(end);
    const large = end - start > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${radius} ${radius} 0 ${large} 1 ${e.x} ${e.y}`;
  }

  const trackPath = describeArc(startAngle, endAngle);
  const fillPath = score > 0 ? describeArc(startAngle, startAngle + fillAngle) : '';

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="140" height="100" viewBox="0 0 140 110">
        {/* Track */}
        <path
          d={trackPath}
          fill="none"
          stroke="currentColor"
          strokeWidth="10"
          strokeLinecap="round"
          className="text-muted/30"
        />
        {/* Fill */}
        {fillPath && (
          <path
            d={fillPath}
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 6px ${color}80)` }}
          />
        )}
        {/* Score text */}
        <text
          x={cx}
          y={cy + 8}
          textAnchor="middle"
          fill={color}
          fontSize="28"
          fontWeight="700"
          fontFamily="'JetBrains Mono', monospace"
          style={{ filter: `drop-shadow(0 0 8px ${color}60)` }}
        >
          {score}
        </text>
        <text x={cx} y={cy + 24} textAnchor="middle" fill="#94A3B8" fontSize="9" fontFamily="inherit">
          / 100
        </text>
      </svg>
      <span
        className={cn(
          'text-xs font-semibold uppercase tracking-widest px-3 py-1 rounded-full border',
          score < 30 && 'text-success border-success/30 bg-success/10',
          score >= 30 && score < 60 && 'text-warning border-warning/30 bg-warning/10',
          score >= 60 && 'text-destructive border-destructive/30 bg-destructive/10',
        )}
      >
        {label}
      </span>
    </div>
  );
}
