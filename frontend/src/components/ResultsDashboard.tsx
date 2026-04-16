import { useCallback, useState } from "react"
import type { FinancialData, UnderwritingResult } from "@/types"
import { AuditorCard, TrendCard, BenchmarkCard } from "./AgentCard"
import { AgentLogs } from "./AgentLogs"
import { HITLPanel } from "./HITLPanel"
import { InsightsCharts } from "./InsightsCharts"
import { ParsedDataCharts } from "./ParsedDataCharts"
import { Separator } from "@/components/ui/separator"
import { AdvancedVisuals } from "./AdvancedVisuals"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import {
  downloadCommitteeChairSynthesisJson,
  downloadCommitteeChairSynthesisPdf,
  hasCommitteeChairExportData,
} from "@/lib/exportCommitteeChairSynthesis"
import { toast } from "sonner"
import { FileDown, FileJson, Layers2, SlidersHorizontal } from "lucide-react"

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
  const [pdfExporting, setPdfExporting] = useState(false)
  const canExportSynthesis = hasCommitteeChairExportData(result)

  const handleExportJson = useCallback(() => {
    if (!canExportSynthesis) return
    try {
      downloadCommitteeChairSynthesisJson(result)
      toast.success("Committee Chair synthesis exported as JSON.")
    } catch {
      toast.error("Could not export JSON.")
    }
  }, [result, canExportSynthesis])

  const handleExportPdf = useCallback(async () => {
    if (!canExportSynthesis) return
    setPdfExporting(true)
    try {
      await downloadCommitteeChairSynthesisPdf(result)
      toast.success("PDF downloaded.")
    } catch {
      toast.error("Could not generate PDF.")
    } finally {
      setPdfExporting(false)
    }
  }, [result, canExportSynthesis])

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
      {/* Uses theme tokens from index.css (--card, --background, --border, --muted) */}
      <Card className="overflow-hidden border border-border/60 bg-card text-card-foreground shadow-sm">
        <CardHeader className="border-b border-[#d1e9e3]/80 bg-[#f0f9f6]/60 pb-4 dark:border-border dark:bg-muted/30">
          <div className="flex min-w-0 items-start gap-3">
            <div className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-border/60 bg-background shadow-sm">
              <SlidersHorizontal className="size-5 text-primary" />
            </div>
            <div className="min-w-0 space-y-1 pt-0.5">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Underwriting decision
              </p>
              <p className="text-base font-semibold leading-snug tracking-tight text-foreground sm:text-lg">
                Suggested annual credit limit
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 bg-card p-5 sm:p-6">
          <div className="rounded-xl border border-[#d1e9e3] bg-[#f0f9f6] p-5 sm:p-6 shadow-[0_1px_2px_rgba(15,23,42,0.04)] dark:border-emerald-900/50 dark:bg-emerald-950/35 dark:shadow-none">
            <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-[#68a691] dark:text-emerald-300">
              Annual limit range
            </p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-[1fr_auto_1fr] sm:items-center sm:gap-0">
              <div className="min-w-0 sm:pr-4">
                <p className="mb-1 text-[10px] uppercase tracking-wider text-[#68a691]/90 dark:text-emerald-400/90">
                  Minimum
                </p>
                <p className="text-2xl font-semibold tabular-nums tracking-tight text-foreground sm:text-3xl">
                  {formatPlainAmount(minLimit)}
                </p>
              </div>
              <div
                className="hidden h-12 w-px shrink-0 self-center bg-[#d1e9e3] dark:bg-emerald-900/50 sm:block"
                aria-hidden
              />
              <div className="min-w-0 border-t border-[#d1e9e3] pt-4 sm:border-t-0 sm:border-l sm:border-[#d1e9e3] sm:pl-4 sm:pt-0 dark:border-emerald-900/40">
                <p className="mb-1 text-[10px] uppercase tracking-wider text-[#68a691]/90 dark:text-emerald-400/90">
                  Maximum
                </p>
                <p className="text-2xl font-semibold tabular-nums tracking-tight text-foreground sm:text-3xl">
                  {formatPlainAmount(maxLimit)}
                </p>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-3 border-t border-[#d1e9e3] pt-4 sm:grid-cols-2 dark:border-emerald-900/40">
              <div>
                <p className="mb-1 text-[10px] uppercase tracking-wider text-[#68a691]/90 dark:text-emerald-400/90">
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
                <p className="mb-1 text-[10px] uppercase tracking-wider text-[#68a691]/90 dark:text-emerald-400/90">
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
          <div className="rounded-xl border border-[#f7e9d5] bg-[#fff9f0] p-5 sm:p-6 shadow-[0_1px_2px_rgba(15,23,42,0.04)] dark:border-amber-900/40 dark:bg-amber-950/30 dark:shadow-none">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-[#c9a45c] dark:text-amber-300">
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
        </CardContent>
      </Card>

      {/* Visual break between decision card (above) and explainability (below) */}
      <div className="py-2">
        <Separator className="bg-border/80" />
      </div>

      <section
        className="rounded-xl border border-[#d1e9e3] bg-[#f0f9f6] p-5 text-card-foreground shadow-sm dark:border-emerald-900/50 dark:bg-emerald-950/25"
        aria-labelledby="cross-data-heading"
      >
        <div
          id="cross-data-heading"
          className="mb-4 flex items-center gap-2 rounded-lg border border-[#d1e9e3] bg-white/80 px-4 py-2.5 dark:border-emerald-900/50 dark:bg-emerald-950/50"
        >
          <Layers2 className="size-4 shrink-0 text-[#68a691] dark:text-emerald-300" aria-hidden />
          <h2 className="text-[10px] font-semibold uppercase tracking-widest text-[#68a691] dark:text-emerald-300">
            Cross-data explainability
          </h2>
        </div>
        <ul className="grid gap-3 sm:grid-cols-1">
          {crossDataHighlights.slice(0, 5).map((point, idx) => (
            <li
              key={idx}
              className="flex gap-3 rounded-xl border border-[#d1e9e3] bg-white px-4 py-3 text-xs leading-relaxed text-foreground shadow-[0_1px_2px_rgba(15,23,42,0.04)] dark:border-emerald-900/40 dark:bg-emerald-950/40 dark:text-foreground/90 dark:shadow-none"
            >
              <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-[#111827] dark:bg-emerald-400" aria-hidden />
              <span>{point}</span>
            </li>
          ))}
          {crossDataHighlights.length === 0 && (
            <li className="rounded-xl border border-dashed border-[#d1e9e3] bg-white/70 px-4 py-3 text-xs text-muted-foreground dark:border-emerald-900/40 dark:bg-emerald-950/30">
              No cross-data highlights were generated for this case.
            </li>
          )}
        </ul>
      </section>
      <div className="space-y-4 rounded-xl border border-border/60 bg-card p-5 shadow-sm dark:border-border">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold tracking-widest text-muted-foreground/60 uppercase">
              Committee Chair Synthesis
            </p>
            <span className="mt-1 inline-block font-mono text-xs text-muted-foreground">
              Confidence {result.committee_chair?.confidence ?? 0}%
            </span>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 gap-1.5 border-border/60 text-xs"
              disabled={!canExportSynthesis || pdfExporting || loading}
              onClick={() => void handleExportPdf()}
            >
              {pdfExporting ? (
                <Spinner className="size-3.5" />
              ) : (
                <FileDown className="size-3.5" />
              )}
              Download PDF
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 gap-1.5 border-border/60 text-xs"
              disabled={!canExportSynthesis || pdfExporting || loading}
              onClick={handleExportJson}
            >
              <FileJson className="size-3.5" />
              Export JSON
            </Button>
          </div>
        </div>
        {result.committee_chair?.final_verdict_rationale && (
          <p className="text-sm leading-relaxed text-foreground/90">
            {result.committee_chair.final_verdict_rationale}
          </p>
        )}
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <div className="rounded-xl border border-[#d1e9e3] bg-[#f0f9f6] p-5 sm:p-6 dark:border-emerald-900/50 dark:bg-emerald-950/35">
            <p className="mb-3 text-[10px] font-semibold tracking-widest text-[#68a691] uppercase dark:text-emerald-300">
              Key Supporting Points
            </p>
            <ul className="space-y-1.5 text-xs text-[#111827] dark:text-foreground/90">
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
          <div className="rounded-xl border border-[#f9e2e2] bg-[#fdf2f2] p-5 sm:p-6 dark:border-red-950/50 dark:bg-red-950/30">
            <p className="mb-3 text-[10px] font-semibold tracking-widest text-[#d57f7f] uppercase dark:text-red-300">
              Key Risks
            </p>
            <ul className="space-y-1.5 text-xs text-[#111827] dark:text-foreground/90">
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
          <div className="rounded-xl border border-[#f7e9d5] bg-[#fff9f0] p-5 sm:p-6 dark:border-amber-950/45 dark:bg-amber-950/25">
            <p className="mb-3 text-[10px] font-semibold tracking-widest text-[#c9a45c] uppercase dark:text-amber-300">
              Conditions If Approved
            </p>
            <ul className="space-y-1.5 text-xs text-[#111827] dark:text-foreground/90">
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
      {/* <AdvancedVisuals result={result} inputData={inputData} /> */}

      {/* HITL Panel */}
      {result.needs_hitl && result.decision_status === "FLAGGED" && (
        <HITLPanel onSubmit={onHITLSubmit} loading={loading} />
      )}

      <Separator className="bg-border/30" />

      <AgentLogs logs={result.agent_logs} />
    </div>
  )
}
