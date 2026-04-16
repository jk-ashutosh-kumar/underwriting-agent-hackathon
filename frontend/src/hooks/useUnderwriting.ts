import { useState, useCallback } from 'react';
import { analyzeApplicationStream, getSampleData, resumeLangGraphFlow, startLangGraphFlow } from '@/lib/api';
import { normalizeFinancialData } from '@/lib/normalizeFinancialData';
import type {
  FinancialData,
  UnderwritingResult,
  AnalyzeRequest,
  FlowProgressPayload,
  LangGraphFlowResponse,
} from '@/types';

type Step = 'idle' | 'ingesting' | 'auditing' | 'trending' | 'benchmarking' | 'deciding' | 'done';

export interface UnderwritingState {
  step: Step;
  result: UnderwritingResult | null;
  error: string | null;
  loading: boolean;
  /** LangGraph-style pipeline (0 = Ingest … 6 = Checkpoint). */
  pipelineActiveIndex: number;
  pipelineSkippedIds: string[];
  pipelineLabel: string | null;
  pipelineDone: boolean;
}

export function useUnderwriting() {
  const [state, setState] = useState<UnderwritingState>({
    step: 'idle',
    result: null,
    error: null,
    loading: false,
    pipelineActiveIndex: -1,
    pipelineSkippedIds: [],
    pipelineLabel: null,
    pipelineDone: false,
  });

  const run = useCallback(
    async (data: FinancialData, region: string, humanResponse?: string) => {
      setState({
        step: 'ingesting',
        result: null,
        error: null,
        loading: true,
        pipelineActiveIndex: 0,
        pipelineSkippedIds: [],
        pipelineLabel: 'Starting governed underwriting flow…',
        pipelineDone: false,
      });

      try {
        const req: AnalyzeRequest = { data, region, human_response: humanResponse ?? '' };
        const useLangGraphPopup = (import.meta.env.VITE_USE_LANGGRAPH_HITL_POPUP ?? 'false') === 'true';

        const applyLangGraphState = (payload: LangGraphFlowResponse) => {
          setState((s) => ({
            ...s,
            pipelineActiveIndex: payload.active_index,
            pipelineLabel: payload.label,
          }));
        };

        if (useLangGraphPopup) {
          setState((s) => ({
            ...s,
            pipelineActiveIndex: 1,
            pipelineLabel: 'LangGraph start: running committee + router',
          }));
          let started: LangGraphFlowResponse;
          try {
            started = await startLangGraphFlow(req);
          } catch {
            // If dedicated LangGraph endpoint is unavailable, keep UX working via stream.
            const onProgress = (ev: FlowProgressPayload) => {
              setState((s) => {
                const merged = new Set(s.pipelineSkippedIds);
                for (const id of ev.skipped_steps ?? []) merged.add(id);
                return {
                  ...s,
                  pipelineActiveIndex: ev.active_index,
                  pipelineLabel: ev.label,
                  pipelineSkippedIds: merged.size > 0 ? Array.from(merged) : s.pipelineSkippedIds,
                };
              });
            };
            const result = await analyzeApplicationStream(req, onProgress);
            setState((s) => ({
              step: 'done',
              result,
              error: null,
              loading: false,
              pipelineActiveIndex: 6,
              pipelineSkippedIds: s.pipelineSkippedIds,
              pipelineLabel: 'Complete',
              pipelineDone: true,
            }));
            return;
          }
          applyLangGraphState(started);

          if (started.status === 'NEEDS_INPUT') {
            setState((s) => ({
              ...s,
              pipelineActiveIndex: 3,
              pipelineLabel: 'Awaiting your clarification (LangGraph HITL)',
            }));
            const flagged = started.hitl_context?.transaction;
            const flaggedReason = started.hitl_context?.message ?? 'Suspicious transaction requires human clarification.';
            const flaggedAmount =
              typeof flagged?.amount === 'number' ? `Amount: ${flagged.amount.toLocaleString()}` : 'Amount: N/A';
            const flaggedDate = flagged?.date ? `Date: ${flagged.date}` : 'Date: N/A';
            const flaggedType = flagged?.type ? `Type: ${String(flagged.type)}` : 'Type: N/A';
            const flaggedDescription = flagged?.description ? `Description: ${flagged.description}` : 'Description: N/A';
            const clarification = window.prompt(
              `Human review required.\n${flaggedReason}\n${flaggedDate}\n${flaggedAmount}\n${flaggedType}\n${flaggedDescription}\n\nPlease explain this flagged transaction:`,
              '',
            );
            if (!clarification || !clarification.trim()) {
              throw new Error('Clarification is required to resume LangGraph flow');
            }
            setState((s) => ({
              ...s,
              pipelineActiveIndex: 4,
              pipelineLabel: 'Resuming LangGraph with your clarification',
            }));
            const resumed = await resumeLangGraphFlow({
              ...req,
              thread_id: started.thread_id,
              human_response: clarification.trim(),
            });
            applyLangGraphState(resumed);
            if (!resumed.result) {
              throw new Error('LangGraph resume finished without final result');
            }
            setState({
              step: 'done',
              result: resumed.result,
              error: null,
              loading: false,
              pipelineActiveIndex: 6,
              pipelineSkippedIds: [],
              pipelineLabel: 'Complete',
              pipelineDone: true,
            });
            return;
          }

          if (!started.result) {
            throw new Error('LangGraph start finished without final result');
          }
          setState({
            step: 'done',
            result: started.result,
            error: null,
            loading: false,
            pipelineActiveIndex: 6,
            pipelineSkippedIds: [],
            pipelineLabel: 'Complete',
            pipelineDone: true,
          });
          return;
        }

        const onProgress = (ev: FlowProgressPayload) => {
          setState((s) => {
            const merged = new Set(s.pipelineSkippedIds);
            for (const id of ev.skipped_steps ?? []) merged.add(id);
            return {
              ...s,
              pipelineActiveIndex: ev.active_index,
              pipelineLabel: ev.label,
              pipelineSkippedIds: merged.size > 0 ? Array.from(merged) : s.pipelineSkippedIds,
            };
          });
        };

        const result = await analyzeApplicationStream(req, onProgress);

        setState((s) => ({
          step: 'done',
          result,
          error: null,
          loading: false,
          pipelineActiveIndex: 6,
          pipelineSkippedIds: s.pipelineSkippedIds,
          pipelineLabel: 'Complete',
          pipelineDone: true,
        }));
      } catch (err) {
        setState({
          step: 'idle',
          result: null,
          error: err instanceof Error ? err.message : 'Analysis failed',
          loading: false,
          pipelineActiveIndex: -1,
          pipelineSkippedIds: [],
          pipelineLabel: null,
          pipelineDone: false,
        });
      }
    },
    [],
  );

  const loadSample = useCallback(async (): Promise<FinancialData | null> => {
    try {
      const raw = await getSampleData();
      return normalizeFinancialData(raw as unknown);
    } catch {
      return null;
    }
  }, []);

  const reset = useCallback(() => {
    setState({
      step: 'idle',
      result: null,
      error: null,
      loading: false,
      pipelineActiveIndex: -1,
      pipelineSkippedIds: [],
      pipelineLabel: null,
      pipelineDone: false,
    });
  }, []);

  return { ...state, run, loadSample, reset };
}
