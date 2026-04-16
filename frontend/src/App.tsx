import { useState, useRef, useCallback, useEffect } from 'react';
import { Toaster } from '@/components/ui/sonner';
import { toast } from 'sonner';
import { Header } from '@/components/Header';
import { InputPanel } from '@/components/InputPanel';
import { ResultsDashboard } from '@/components/ResultsDashboard';
import { PipelineFlow } from '@/components/PipelineFlow';
import { EmptyState } from '@/components/EmptyState';
import { HITLDialog } from '@/components/HITLDialog';
import { useUnderwriting } from '@/hooks/useUnderwriting';
import { useTheme } from '@/components/theme-provider';
import type { FinancialData } from '@/types';
import type { HITLContext } from '@/components/HITLDialog';
import type { HITLPromptFn } from '@/hooks/useUnderwriting';

export default function App() {
  const { theme } = useTheme();
  const {
    result,
    error,
    loading,
    run,
    reset,
    pipelineActiveIndex,
    pipelineSkippedIds,
    pipelineLabel,
    pipelineDone,
  } = useUnderwriting();

  const [lastData, setLastData] = useState<{ data: FinancialData; region: string } | null>(null);
  const [hitlContext, setHitlContext] = useState<HITLContext | null>(null);
  const hitlResolverRef = useRef<((value: string) => void) | null>(null);
  /** Delayed flag — true ~900ms after pipelineDone so overlay exit plays first */
  const [showResults, setShowResults] = useState(false);

  useEffect(() => {
    if (pipelineDone && result) {
      const t = setTimeout(() => setShowResults(true), 900);
      return () => clearTimeout(t);
    } else {
      setShowResults(false);
    }
  }, [pipelineDone, result]);

  /** Promise-based HITL prompt: shows dialog, pauses until user submits */
  const onHITLPrompt = useCallback<HITLPromptFn>((context) => {
    setHitlContext(context);
    return new Promise<string>((resolve) => {
      hitlResolverRef.current = resolve;
    });
  }, []);

  function handleHITLSubmit(clarification: string) {
    setHitlContext(null);
    hitlResolverRef.current?.(clarification);
    hitlResolverRef.current = null;
  }

  function handleHITLCancel() {
    setHitlContext(null);
    hitlResolverRef.current?.('');
    hitlResolverRef.current = null;
  }

  async function handleRun(data: FinancialData, region: string) {
    setLastData({ data, region });
    await run(data, region, undefined, onHITLPrompt);
  }

  async function handleHITL(response: string) {
    if (!lastData) return;
    toast.info('Re-running with clarification...');
    await run(lastData.data, lastData.region, response, onHITLPrompt);
  }

  if (error) {
    toast.error(error);
  }

  return (
    <div className="min-h-screen bg-background text-foreground relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(37,99,235,0.09),transparent_45%),radial-gradient(circle_at_80%_0%,rgba(14,165,233,0.07),transparent_38%)]" />
      <Header />

      {/* Fullscreen pipeline overlay — visible while loading, disappears when done */}
      {pipelineActiveIndex >= 0 && (
        <PipelineFlow
          activeIndex={pipelineActiveIndex}
          skippedStepIds={pipelineSkippedIds}
          done={pipelineDone}
          progressLabel={pipelineLabel}
        />
      )}

      {/* HITL dialog — renders above the pipeline overlay */}
      <HITLDialog
        context={hitlContext}
        onSubmit={handleHITLSubmit}
        onCancel={handleHITLCancel}
      />

      <main className="pt-14 min-h-screen flex flex-col relative">
        <div className="flex-1 flex gap-4 px-6 py-6 max-w-[1760px] mx-auto w-full">
          <InputPanel
            onRun={handleRun}
            onReset={reset}
            loading={loading}
            hasResult={!!result}
          />
          <div className="w-px bg-border/40 shrink-0" />
          {result && showResults ? (
            <ResultsDashboard
              result={result}
              inputData={lastData?.data ?? null}
              onHITLSubmit={handleHITL}
              loading={loading}
            />
          ) : (
            <EmptyState />
          )}
        </div>
      </main>

      <Toaster position="bottom-right" richColors theme={theme === "system" ? "light" : theme} />
    </div>
  );
}
