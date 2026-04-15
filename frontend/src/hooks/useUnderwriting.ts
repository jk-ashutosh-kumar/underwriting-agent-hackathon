import { useState, useCallback } from 'react';
import { analyzeApplication, getSampleData } from '@/lib/api';
import type { FinancialData, UnderwritingResult, AnalyzeRequest } from '@/types';

type Step = 'idle' | 'ingesting' | 'auditing' | 'trending' | 'benchmarking' | 'deciding' | 'done';

export interface UnderwritingState {
  step: Step;
  result: UnderwritingResult | null;
  error: string | null;
  loading: boolean;
}

export function useUnderwriting() {
  const [state, setState] = useState<UnderwritingState>({
    step: 'idle',
    result: null,
    error: null,
    loading: false,
  });

  const run = useCallback(
    async (data: FinancialData, region: string, humanResponse?: string) => {
      setState({ step: 'ingesting', result: null, error: null, loading: true });

      const steps: Step[] = ['auditing', 'trending', 'benchmarking', 'deciding'];
      let stepIdx = 0;

      const ticker = setInterval(() => {
        if (stepIdx < steps.length) {
          setState((s) => ({ ...s, step: steps[stepIdx++] }));
        }
      }, 1200);

      try {
        const req: AnalyzeRequest = { data, region, human_response: humanResponse ?? '' };
        const result = await analyzeApplication(req);
        clearInterval(ticker);
        setState({ step: 'done', result, error: null, loading: false });
      } catch (err) {
        clearInterval(ticker);
        setState({
          step: 'idle',
          result: null,
          error: err instanceof Error ? err.message : 'Analysis failed',
          loading: false,
        });
      }
    },
    [],
  );

  const loadSample = useCallback(async (): Promise<FinancialData | null> => {
    try {
      return await getSampleData();
    } catch {
      return null;
    }
  }, []);

  const reset = useCallback(() => {
    setState({ step: 'idle', result: null, error: null, loading: false });
  }, []);

  return { ...state, run, loadSample, reset };
}
