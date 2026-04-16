import { useState, useCallback } from 'react';
import { analyzeApplicationStream, resumeLangGraphFlow, startLangGraphFlow } from '@/lib/api';
import type {
  FinancialData,
  UnderwritingResult,
  AnalyzeRequest,
  FlowProgressPayload,
  LangGraphFlowResponse,
} from '@/types';
import type { HITLContext } from '@/components/HITLDialog';

/** Async callback provided by the UI to collect the user's HITL clarification. */
export type HITLPromptFn = (context: HITLContext) => Promise<string>;

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

  /** Sweep the pipeline indicator through steps startIdx → 6 with a per-step delay, then mark done. */
  const animateSweep = useCallback(
    (startIdx: number, stepMs = 700): Promise<void> =>
      new Promise((resolve) => {
        let i = startIdx;
        const labels = ['Resuming flow…', 'Running decision engine…', 'Saving checkpoint…', 'Complete'];
        function next() {
          if (i > 6) {
            resolve();
            return;
          }
          const label = labels[Math.max(0, i - 4)] ?? 'Processing…';
          setState((s) => ({ ...s, pipelineActiveIndex: i, pipelineLabel: label }));
          i++;
          setTimeout(next, stepMs);
        }
        next();
      }),
    [],
  );

  function randIntInclusive(min: number, max: number) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  async function cinematicSweep(startIdx: number, totalMinMs: number, totalMaxMs: number) {
    const totalMs = randIntInclusive(totalMinMs, totalMaxMs);
    const steps = Math.max(1, 6 - startIdx + 1);
    const stepMs = Math.max(450, Math.round(totalMs / steps));
    await animateSweep(startIdx, stepMs);
  }

  async function promptHITL(onHITLPrompt: HITLPromptFn | undefined): Promise<string> {
    const hitlContext: HITLContext = {
      message: 'Human review is required to continue. Please add clarification for the flagged activity.',
    };
    const clarification = onHITLPrompt
      ? await onHITLPrompt(hitlContext)
      : window.prompt(
        `Human review required.\n${hitlContext.message}\n\nPlease provide clarification:`,
        '',
      ) ?? '';
    return clarification.trim();
  }

  const run = useCallback(
    async (data: FinancialData, region: string, humanResponse?: string, onHITLPrompt?: HITLPromptFn) => {
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
            const hitlContext: HITLContext = {
              message: started.hitl_context?.message ?? 'Suspicious transaction requires human clarification.',
              transaction: flagged ? {
                amount: typeof flagged.amount === 'number' ? flagged.amount : undefined,
                date: flagged.date ? String(flagged.date) : undefined,
                type: flagged.type ? String(flagged.type) : undefined,
                description: flagged.description ? String(flagged.description) : undefined,
              } : undefined,
            };
            const clarification = onHITLPrompt
              ? await onHITLPrompt(hitlContext)
              : window.prompt(
                `Human review required.\n${hitlContext.message}\n\nPlease explain this flagged transaction:`,
                '',
              ) ?? '';
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
            // Animate sweep through remaining steps, then reveal results
            await animateSweep(5);
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

        let hitlTransitionTimer: number | null = null;

        const onProgress = (ev: FlowProgressPayload) => {
          // If backend signals a HITL pause right after committee/decision,
          // briefly show the router step so the UI "moves" into HITL.
          if (ev.human_in_loop && !humanResponse && hitlTransitionTimer == null) {
            setState((s) => ({
              ...s,
              pipelineActiveIndex: 2,
              pipelineLabel: 'Routing to human review…',
            }));
            hitlTransitionTimer = window.setTimeout(() => {
              setState((s) => ({
                ...s,
                pipelineActiveIndex: 3,
                pipelineLabel: 'Human review required (HITL)',
              }));
            }, 900);
          }

          setState((s) => {
            const merged = new Set(s.pipelineSkippedIds);
            for (const id of ev.skipped_steps ?? []) merged.add(id);
            const shouldPauseForHITL = !!ev.human_in_loop;
            return {
              ...s,
              pipelineActiveIndex: shouldPauseForHITL ? 3 : ev.active_index,
              pipelineLabel: shouldPauseForHITL ? 'Human review required (HITL)' : ev.label,
              pipelineSkippedIds: merged.size > 0 ? Array.from(merged) : s.pipelineSkippedIds,
            };
          });
        };

        const result = await analyzeApplicationStream(req, onProgress);

        // Stream mode HITL: if backend flags the case, pause at HITL and collect user input,
        // then animate through remaining steps before revealing the final dashboard.
        if (result.needs_hitl && !humanResponse) {
          setState((s) => ({
            ...s,
            step: 'deciding',
            result: null,
            loading: false,
            pipelineActiveIndex: 3,
            pipelineLabel: 'Awaiting your clarification (HITL)',
            pipelineDone: false,
          }));

          const clarification = await promptHITL(onHITLPrompt);
          if (!clarification) {
            throw new Error('Clarification is required to resume the underwriting flow');
          }

          setState((s) => ({
            ...s,
            pipelineActiveIndex: 4,
            pipelineLabel: 'Resuming with your clarification…',
            loading: true,
          }));

          const resumed = await analyzeApplicationStream(
            { ...req, human_response: clarification },
            onProgress,
          );

          // Post-HITL: “pass through all processes” animation (5–15s total)
          await cinematicSweep(4, 5000, 15000);

          setState((s) => ({
            step: 'done',
            result: resumed,
            error: null,
            loading: false,
            pipelineActiveIndex: 6,
            pipelineSkippedIds: s.pipelineSkippedIds,
            pipelineLabel: 'Complete',
            pipelineDone: true,
          }));
          return;
        }

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

  return { ...state, run, reset };
}
