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
    <div className="relative min-h-screen overflow-x-hidden bg-background text-foreground">
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

      <main className="relative pt-16">
        {/* Sidebar: fixed on lg+; stacks above content on smaller screens */}
        <aside
          className="z-30 w-full border-b border-border/40 bg-card/95 backdrop-blur-md lg:fixed lg:top-16 lg:bottom-0 lg:left-0 lg:w-[420px] lg:border-b-0 lg:border-r lg:overflow-y-auto lg:overscroll-y-contain [scrollbar-gutter:stable]"
        >
          <div className="mx-auto w-full max-w-[420px] px-6 py-6 lg:mx-0 lg:max-w-none">
            <InputPanel
              onRun={handleRun}
              onReset={reset}
              loading={loading}
              hasResult={!!result}
            />
          </div>
        </aside>

        {/* Main column: offset by sidebar width on lg+; only this region scrolls vertically */}
        <div className="flex min-h-0 flex-col lg:ml-[420px] lg:h-[calc(100vh-4rem)]">
          <div className="mx-auto flex min-h-0 w-full max-w-[1760px] flex-1 flex-col px-6 py-6">
            <div className="min-h-0 flex-1 overflow-y-auto scroll-smooth overscroll-y-contain [scrollbar-gutter:stable]">
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
          </div>
        </div>
      </main>

      <Toaster position="bottom-right" richColors theme={theme === "system" ? "light" : theme} />
    </div>
  );
}
