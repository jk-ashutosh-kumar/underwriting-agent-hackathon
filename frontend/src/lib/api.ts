import type { AnalyzeRequest, FinancialData, PersistenceDebug, UnderwritingResult } from '@/types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8010';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Unknown error');
  }
  return res.json() as Promise<T>;
}

export async function getSampleData(): Promise<FinancialData> {
  const res = await fetch(`${API_BASE}/api/sample`);
  return handleResponse<FinancialData>(res);
}

export async function getRegions(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/regions`);
  return handleResponse<string[]>(res);
}

export async function analyzeApplication(req: AnalyzeRequest): Promise<UnderwritingResult> {
  const res = await fetch(`${API_BASE}/api/underwrite`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  return handleResponse<UnderwritingResult>(res);
}

export async function parseDocument(fileName: string, fileType: 'pdf' | 'json'): Promise<FinancialData> {
  const res = await fetch(`${API_BASE}/api/parse-document`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_name: fileName, file_type: fileType }),
  });
  return handleResponse<FinancialData>(res);
}

export async function getPersistenceDebug(): Promise<PersistenceDebug> {
  const res = await fetch(`${API_BASE}/api/debug/persistence`);
  return handleResponse<PersistenceDebug>(res);
}
