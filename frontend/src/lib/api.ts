import type {
  AnalyzeRequest,
  CaseDocument,
  CompanyCaseSummary,
  FlowProgressPayload,
  IngestResponse,
  LangGraphFlowResponse,
  PersistenceDebug,
  UnderwritingResult,
} from '@/types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8010';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Unknown error');
  }
  return res.json() as Promise<T>;
}

export async function analyzeApplication(req: AnalyzeRequest): Promise<UnderwritingResult> {
  const res = await fetch(`${API_BASE}/api/underwrite`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  return handleResponse<UnderwritingResult>(res);
}

/**
 * Run full governed flow with NDJSON progress (LangGraph stages + HITL when applicable).
 */
export async function analyzeApplicationStream(
  req: AnalyzeRequest,
  onProgress: (event: FlowProgressPayload) => void,
): Promise<UnderwritingResult> {
  const res = await fetch(`${API_BASE}/api/underwrite/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Unknown error');
  }
  const reader = res.body?.getReader();
  if (!reader) {
    throw new Error('No response body from underwriting stream');
  }
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const obj = JSON.parse(trimmed) as Record<string, unknown>;
      if (obj.type === 'progress') {
        onProgress(obj as unknown as FlowProgressPayload);
      } else if (obj.type === 'result') {
        return (obj as { payload: UnderwritingResult }).payload;
      } else if (obj.type === 'error') {
        throw new Error(String((obj as { message?: string }).message ?? 'Stream error'));
      }
    }
  }
  throw new Error('Stream ended without result');
}

export async function startLangGraphFlow(req: AnalyzeRequest): Promise<LangGraphFlowResponse> {
  const res = await fetch(`${API_BASE}/api/underwrite/langgraph/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  return handleResponse<LangGraphFlowResponse>(res);
}

export async function resumeLangGraphFlow(req: AnalyzeRequest): Promise<LangGraphFlowResponse> {
  const res = await fetch(`${API_BASE}/api/underwrite/langgraph/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  return handleResponse<LangGraphFlowResponse>(res);
}

export async function getPersistenceDebug(): Promise<PersistenceDebug> {
  const res = await fetch(`${API_BASE}/api/debug/persistence`);
  return handleResponse<PersistenceDebug>(res);
}

export async function getCompanies(): Promise<CompanyCaseSummary[]> {
  const res = await fetch(`${API_BASE}/api/companies`);
  return handleResponse<CompanyCaseSummary[]>(res);
}

export async function uploadCompanyDocuments(companyId: string, files: File[]): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append('company_id', companyId);
  for (const file of files) {
    formData.append('files', file);
  }
  const res = await fetch(`${API_BASE}/api/parse-document`, {
    method: 'POST',
    body: formData,
  });
  return handleResponse<IngestResponse>(res);
}

export async function getCaseDocuments(caseId: string): Promise<CaseDocument[]> {
  const res = await fetch(`${API_BASE}/api/case/${caseId}/documents`);
  return handleResponse<CaseDocument[]>(res);
}
