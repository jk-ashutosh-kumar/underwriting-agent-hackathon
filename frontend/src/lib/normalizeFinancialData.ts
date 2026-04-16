import type { FinancialData, Transaction } from '@/types';

function mapTxnRow(t: Record<string, unknown>): Transaction {
  const amount = typeof t.amount === 'number' ? t.amount : Number(t.amount ?? 0);
  const transactionType: 'credit' | 'debit' = t.type === 'credit' ? 'credit' : 'debit';
  const description =
    typeof t.description === 'string'
      ? t.description
      : typeof t.desc === 'string'
        ? t.desc
        : String(t.description ?? t.desc ?? '');
  return {
    date: String(t.date ?? ''),
    description,
    amount: Number.isFinite(amount) ? amount : 0,
    type: transactionType,
  };
}

/**
 * Accepts flat statement JSON or SME-style `monthly_data` + `annual_summary` payloads
 * and returns the shape the API and UI expect.
 */
export function normalizeFinancialData(value: unknown): FinancialData | null {
  if (!value || typeof value !== 'object') return null;
  const obj = value as Record<string, unknown>;

  // SME / extended schema: monthly_data[].major_transactions[]
  if (Array.isArray(obj.monthly_data) && !Array.isArray(obj.transactions)) {
    const months = obj.monthly_data.filter((m): m is Record<string, unknown> => !!m && typeof m === 'object');
    const transactions: Transaction[] = [];
    for (const m of months) {
      const txs = m.major_transactions;
      if (!Array.isArray(txs)) continue;
      for (const raw of txs) {
        if (!raw || typeof raw !== 'object') continue;
        transactions.push(mapTxnRow(raw as Record<string, unknown>));
      }
    }
    const annual = obj.annual_summary;
    let totalInflow = 0;
    let totalOutflow = 0;
    if (annual && typeof annual === 'object') {
      const a = annual as Record<string, unknown>;
      if (typeof a.total_annual_inflow === 'number') totalInflow = a.total_annual_inflow;
      if (typeof a.total_annual_outflow === 'number') totalOutflow = a.total_annual_outflow;
    }
    if (!totalInflow || !totalOutflow) {
      for (const m of months) {
        if (typeof m.total_inflow === 'number') totalInflow += m.total_inflow;
        if (typeof m.total_outflow === 'number') totalOutflow += m.total_outflow;
      }
    }
    if (!Number.isFinite(totalInflow) || !Number.isFinite(totalOutflow)) return null;
    if (transactions.length === 0) return null;

    return {
      applicant_id: typeof obj.applicant_id === 'string' ? obj.applicant_id : undefined,
      statement_month:
        typeof obj.fiscal_year === 'string'
          ? obj.fiscal_year
          : typeof obj.statement_month === 'string'
            ? obj.statement_month
            : undefined,
      transactions,
      total_inflow: totalInflow,
      total_outflow: totalOutflow,
    };
  }

  // Flat schema
  if (!Array.isArray(obj.transactions)) return null;
  if (typeof obj.total_inflow !== 'number' || Number.isNaN(obj.total_inflow)) return null;
  if (typeof obj.total_outflow !== 'number' || Number.isNaN(obj.total_outflow)) return null;

  const transactions = obj.transactions
    .filter((t): t is Record<string, unknown> => !!t && typeof t === 'object')
    .map((t) => mapTxnRow(t));

  return {
    applicant_id: typeof obj.applicant_id === 'string' ? obj.applicant_id : undefined,
    statement_month: typeof obj.statement_month === 'string' ? obj.statement_month : undefined,
    transactions,
    total_inflow: obj.total_inflow,
    total_outflow: obj.total_outflow,
  };
}
