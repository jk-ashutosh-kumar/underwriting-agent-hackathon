import type { FinancialData, UnderwritingResult } from "@/types"
import { AuditorCard, TrendCard, BenchmarkCard } from "./AgentCard"
import { AgentLogs } from "./AgentLogs"
import { HITLPanel } from "./HITLPanel"
import { InsightsCharts } from "./InsightsCharts"
import { ParsedDataCharts } from "./ParsedDataCharts"
import { Separator } from "@/components/ui/separator"
import { AdvancedVisuals } from "./AdvancedVisuals"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { Layers2, SlidersHorizontal } from "lucide-react"

/** Plain amount: no symbol, no grouping; avoids float artifacts like trailing dots. */
function formatPlainAmount(value: number): string {
  if (!Number.isFinite(value)) return "0"
  return new Intl.NumberFormat("en-US", {
    useGrouping: false,
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  }).format(value)
}

interface ResultsDashboardProps {
  result: UnderwritingResult
  inputData: FinancialData | null
  onHITLSubmit: (response: string) => void
  loading: boolean
}

export function ResultsDashboard({
  result,
  inputData,
  onHITLSubmit,
  loading,
}: ResultsDashboardProps) {
  const minLimit = Math.round(result.credit_limit?.min_limit ?? 0)
  const maxLimit = Math.round(result.credit_limit?.max_limit ?? 0)
  const econBase = Math.round(result.credit_limit?.economics_base_limit ?? 0)
  const nominalCeil = Math.round(result.credit_limit?.nominal_ceiling ?? 0)
  const creditLimitReasoning = result.credit_limit?.reasoning ?? ""
  const crossDataHighlights = [
    ...(result.audit?.flags ?? []).slice(0, 2),
    result.trend?.insight,
    result.benchmark?.comparison ?? result.benchmark?.comparison_insight,
  ].filter((item): item is string => Boolean(item && item.trim()))

  return (
    <div className="min-w-0 flex-1 space-y-5">
      <Card
        className={cn(
          "border-border/60 bg-elevated shadow-none",
          "bg-gradient-to-br from-primary/[0.06] via-elevated to-elevated",
        )}
      >
          <CardHeader className="pb-3">
            <div className="flex min-w-0 items-start gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10">
                <SlidersHorizontal className="size-5 text-primary" />
              </div>
              <div className="min-w-0 space-y-1">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Underwriting decision
                </p>
                <p className="text-sm font-semibold leading-snug text-foreground">
                  Suggested annual credit limit
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5 pt-0">
            <div className="grid gap-4 sm:gap-5">
              <div className="rounded-xl border border-border/60 bg-muted/10 p-4">
                <p className="mb-4 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                  Annual limit range
                </p>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-[1fr_auto_1fr] sm:items-center sm:gap-0">
                  <div className="min-w-0 sm:pr-4">
                    <p className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Minimum</p>
                    <p className="text-2xl font-semibold tabular-nums tracking-tight text-foreground sm:text-3xl">
                      {formatPlainAmount(minLimit)}
                    </p>
                  </div>
                  <div
                    className="hidden h-12 w-px shrink-0 self-center bg-border/70 sm:block"
                    aria-hidden
                  />
                  <div className="min-w-0 border-t border-border/50 pt-4 sm:border-t-0 sm:border-l sm:pl-4 sm:pt-0">
                    <p className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Maximum</p>
                    <p className="text-2xl font-semibold tabular-nums tracking-tight text-foreground sm:text-3xl">
                      {formatPlainAmount(maxLimit)}
                    </p>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-1 gap-3 border-t border-border/40 pt-4 sm:grid-cols-2">
                  <div>
                    <p className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                      Economics base (25% anchor)
                    </p>
                    <p className="text-lg font-semibold tabular-nums tracking-tight text-foreground">
                      {formatPlainAmount(econBase)}
                    </p>
                    <p className="mt-1 text-[10px] leading-snug text-muted-foreground">
                      Rule-of-thumb from modeled annual flow before final policy.
                    </p>
                  </div>
                  <div>
                    <p className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                      Nominal ceiling (pre-policy)
                    </p>
                    <p className="text-lg font-semibold tabular-nums tracking-tight text-foreground">
                      {formatPlainAmount(nominalCeil)}
                    </p>
                    <p className="mt-1 text-[10px] leading-snug text-muted-foreground">
                      Top of the economics-only band; maximum the model would allow before haircuts.
                    </p>
                  </div>
                </div>
              </div>
              <div className="rounded-xl border border-border/50 bg-muted/15 p-4">
                <p className="mb-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                  Why this range
                </p>
                {creditLimitReasoning ? (
                  <p className="whitespace-pre-line text-xs leading-relaxed text-foreground/90">
                    {creditLimitReasoning}
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Credit limit reasoning was not provided for this case.
                  </p>
                )}
              </div>
            </div>

            <div className="border-t border-border/40 pt-4">
              <div className="mb-3 flex items-center gap-2">
                <Layers2 className="size-3.5 text-muted-foreground" />
                <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Cross-data explainability
                </p>
              </div>
              <ul className="grid gap-2 sm:grid-cols-1">
                {crossDataHighlights.slice(0, 5).map((point, idx) => (
                  <li
                    key={idx}
                    className="flex gap-3 rounded-lg border border-border/40 bg-background/40 px-3 py-2.5 text-xs leading-relaxed text-foreground/90"
                  >
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary/70" aria-hidden />
                    <span>{point}</span>
                  </li>
                ))}
                {crossDataHighlights.length === 0 && (
                  <li className="rounded-lg border border-dashed border-border/60 px-3 py-3 text-xs text-muted-foreground">
                    No cross-data highlights were generated for this case.
                  </li>
                )}
              </ul>
            </div>
          </CardContent>
        </Card>
      <div className="space-y-3 rounded-xl border border-border/60 bg-elevated p-4">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-semibold tracking-widest text-muted-foreground/60 uppercase">
            Committee Chair Synthesis
          </p>
          <span className="font-mono text-xs text-muted-foreground">
            Confidence {result.committee_chair?.confidence ?? 0}%
          </span>
        </div>
        {result.committee_chair?.final_verdict_rationale && (
          <p className="text-sm leading-relaxed text-foreground/90">
            {result.committee_chair.final_verdict_rationale}
          </p>
        )}
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          <div className="rounded-lg border border-success/25 bg-success/5 p-3">
            <p className="mb-2 text-[10px] tracking-widest text-success/80 uppercase">
              Key Supporting Points
            </p>
            <ul className="space-y-1 text-xs text-foreground/85">
              {(result.committee_chair?.key_supporting_points ?? [])
                .slice(0, 3)
                .map((point, idx) => (
                  <li key={idx}>• {point}</li>
                ))}
              {(result.committee_chair?.key_supporting_points ?? []).length ===
                0 && (
                <li className="text-muted-foreground">
                  • No explicit supporting points returned.
                </li>
              )}
            </ul>
          </div>
          <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-3">
            <p className="mb-2 text-[10px] tracking-widest text-destructive/80 uppercase">
              Key Risks
            </p>
            <ul className="space-y-1 text-xs text-foreground/85">
              {(result.committee_chair?.key_risks ?? [])
                .slice(0, 3)
                .map((point, idx) => (
                  <li key={idx}>• {point}</li>
                ))}
              {(result.committee_chair?.key_risks ?? []).length === 0 && (
                <li className="text-muted-foreground">
                  • No explicit risk points returned.
                </li>
              )}
            </ul>
          </div>
        </div>
        {(result.committee_chair?.conditions_if_approved ?? []).length > 0 && (
          <div className="rounded-lg border border-warning/25 bg-warning/5 p-3">
            <p className="mb-2 text-[10px] tracking-widest text-warning/80 uppercase">
              Conditions If Approved
            </p>
            <ul className="space-y-1 text-xs text-foreground/85">
              {result.committee_chair.conditions_if_approved.map(
                (condition, idx) => (
                  <li key={idx}>• {condition}</li>
                )
              )}
            </ul>
          </div>
        )}
      </div>
      <div>
        <p className="mb-3 text-[10px] font-semibold tracking-widest text-muted-foreground/60 uppercase">
          Agent Committee Output
        </p>
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
          <AuditorCard data={result.audit} />
          <TrendCard data={result.trend} />
          <BenchmarkCard data={result.benchmark} />
        </div>
      </div>

      <InsightsCharts result={result} />
      {inputData && <ParsedDataCharts data={inputData} />}
      <AdvancedVisuals result={result} inputData={inputData} />

      {/* HITL Panel */}
      {result.needs_hitl && result.decision_status === "FLAGGED" && (
        <HITLPanel onSubmit={onHITLSubmit} loading={loading} />
      )}

      <Separator className="bg-border/30" />

      <AgentLogs logs={result.agent_logs} />
    </div>
  )
}
