import { useState } from 'react';
import { Toaster } from '@/components/ui/sonner';
import { toast } from 'sonner';
import { Header } from '@/components/Header';
import { InputPanel } from '@/components/InputPanel';
import { ResultsDashboard } from '@/components/ResultsDashboard';
import { PipelineFlow } from '@/components/PipelineFlow';
import { EmptyState } from '@/components/EmptyState';
import { useUnderwriting } from '@/hooks/useUnderwriting';
import type { FinancialData } from '@/types';

export default function App() {
  const { step, result, error, loading, run, loadSample, reset } = useUnderwriting();
  const [lastData, setLastData] = useState<{ data: FinancialData; region: string } | null>(null);

  async function handleRun(data: FinancialData, region: string) {
    setLastData({ data, region });
    await run(data, region);
  }

  async function handleHITL(response: string) {
    if (!lastData) return;
    toast.info('Re-running with clarification...');
    await run(lastData.data, lastData.region, response);
  }

  if (error) {
    toast.error(error);
  }

  return (
    <div className="min-h-screen bg-background text-foreground relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(37,99,235,0.09),transparent_45%),radial-gradient(circle_at_80%_0%,rgba(14,165,233,0.07),transparent_38%)]" />
      <Header />
      <main className="pt-14 min-h-screen flex flex-col relative">
        {step !== 'idle' && (
          <div className="border-b border-border/40 bg-muted/5 px-6 py-3">
            <PipelineFlow currentStep={step} />
          </div>
        )}
        <div className="flex-1 flex gap-4 px-6 py-6 max-w-[1760px] mx-auto w-full">
          <InputPanel
            onRun={handleRun}
            onLoadSample={loadSample}
            onReset={reset}
            loading={loading}
            hasResult={!!result}
          />
          <div className="w-px bg-border/40 shrink-0" />
          {result ? (
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
      <Toaster position="bottom-right" richColors theme="light" />
    </div>
  );
}
