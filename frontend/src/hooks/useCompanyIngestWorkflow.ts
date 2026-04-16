import { useCallback, useEffect, useRef, useState } from 'react';
import { getCaseDocuments, getCompanies, uploadCompanyDocuments } from '@/lib/api';
import { normalizeFinancialData } from '@/lib/normalizeFinancialData';
import type { CaseDocument, CompanyCaseSummary, FinancialData, IngestResponse } from '@/types';

export const MAX_UPLOAD_FILES = 3;
const POLL_MS = 1500;
const EXTRACT_MAX_ATTEMPTS = 120;

export type WorkflowUiPhase =
  | 'loading_companies'
  | 'pick_company'
  | 'idle_ready_upload'
  | 'uploading'
  | 'extracting'
  | 'error';

function mergeFinancialData(dataList: FinancialData[]): FinancialData {
  const transactions = dataList.flatMap((d) => d.transactions ?? []);
  const total_inflow = dataList.reduce((sum, d) => sum + d.total_inflow, 0);
  const total_outflow = dataList.reduce((sum, d) => sum + d.total_outflow, 0);
  const applicantIds = Array.from(new Set(dataList.map((d) => d.applicant_id).filter(Boolean)));
  const statementMonths = Array.from(new Set(dataList.map((d) => d.statement_month).filter(Boolean)));

  return {
    applicant_id: applicantIds.length === 1 ? applicantIds[0] : undefined,
    statement_month: statementMonths.length === 1 ? statementMonths[0] : undefined,
    transactions,
    total_inflow,
    total_outflow,
  };
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function normalizeDocStatus(s: string | null | undefined) {
  return (s || '').trim().toLowerCase();
}

function isExtractionSuccessStatus(status: string | null | undefined): boolean {
  const s = normalizeDocStatus(status);
  return s === 'done' || s === 'completed' || s === 'success' || s === 'succeeded';
}

function isExtractionFailedStatus(status: string | null | undefined): boolean {
  const s = normalizeDocStatus(status);
  return s === 'failed' || s === 'error';
}

function allowedUploadFile(file: File): boolean {
  const lower = file.name.toLowerCase();
  if (
    lower.endsWith('.pdf') ||
    lower.endsWith('.json') ||
    lower.endsWith('.png') ||
    lower.endsWith('.jpg') ||
    lower.endsWith('.jpeg') ||
    lower.endsWith('.xlsx')
  ) {
    return true;
  }
  const t = (file.type || '').toLowerCase();
  return (
    t === 'application/pdf' ||
    t === 'application/json' ||
    t === 'text/json' ||
    t === 'image/png' ||
    t === 'image/jpeg' ||
    t === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  );
}

export function useCompanyIngestWorkflow() {
  const [companies, setCompanies] = useState<CompanyCaseSummary[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(true);
  const [companiesError, setCompaniesError] = useState<string | null>(null);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(null);
  const [phase, setPhase] = useState<WorkflowUiPhase>('loading_companies');
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [workflowHint, setWorkflowHint] = useState<string | null>(null);
  const [activeIngest, setActiveIngest] = useState<IngestResponse | null>(null);
  const [extractionPulseStep, setExtractionPulseStep] = useState(0);
  const abortRef = useRef(false);

  const refreshCompanies = useCallback(async () => {
    setCompaniesLoading(true);
    setCompaniesError(null);
    try {
      const rows = await getCompanies();
      setCompanies(rows);
      setPhase((prev) => (prev === 'loading_companies' ? 'pick_company' : prev));
    } catch (e) {
      setCompaniesError(e instanceof Error ? e.message : 'Failed to load companies');
      setCompanies([]);
      setPhase('error');
    } finally {
      setCompaniesLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshCompanies();
  }, [refreshCompanies]);

  useEffect(() => {
    if (phase !== 'extracting') {
      setExtractionPulseStep(0);
      return;
    }
    const id = window.setInterval(() => {
      setExtractionPulseStep((s) => (s < 5 ? s + 1 : 5));
    }, 700);
    return () => window.clearInterval(id);
  }, [phase]);

  const selectCompany = useCallback((id: string | null) => {
    abortRef.current = true;
    setSelectedCompanyId(id);
    setWorkflowError(null);
    setWorkflowHint(null);
    setActiveIngest(null);
    if (id) setPhase('idle_ready_upload');
    else setPhase('pick_company');
  }, []);

  const resetWorkflow = useCallback(() => {
    abortRef.current = true;
    setSelectedCompanyId(null);
    setWorkflowError(null);
    setWorkflowHint(null);
    setActiveIngest(null);
    setExtractionPulseStep(0);
    setPhase('pick_company');
    void refreshCompanies();
  }, [refreshCompanies]);

  const validateFilesForUpload = useCallback(
    (files: File[]): string | null => {
      if (!selectedCompanyId) return 'Select a company before uploading documents.';
      if (files.length === 0) return 'No files selected.';
      if (files.length > MAX_UPLOAD_FILES) {
        return `You can upload at most ${MAX_UPLOAD_FILES} files at once.`;
      }
      for (const f of files) {
        if (!allowedUploadFile(f)) {
          return `Unsupported type: ${f.name}. Use PDF, JSON, PNG, JPEG, or XLSX.`;
        }
      }
      return null;
    },
    [selectedCompanyId],
  );

  const waitForMatchedExtraction = useCallback(
    async (caseId: string, documentIds: string[], fileCount: number): Promise<FinancialData> => {
      for (let attempt = 0; attempt < EXTRACT_MAX_ATTEMPTS; attempt++) {
        if (abortRef.current) throw new Error('Workflow cancelled.');
        const docs = await getCaseDocuments(caseId);
        const tracked = documentIds
          .map((id) => docs.find((d) => d.document_id === id))
          .filter((d): d is CaseDocument => !!d);

        if (tracked.length !== documentIds.length || tracked.length !== fileCount) {
          setWorkflowHint(
            `Waiting for document rows… (${tracked.length}/${documentIds.length} matched by id)`,
          );
          await sleep(POLL_MS);
          continue;
        }

        const formatFailedDetails = (docs: CaseDocument[]) =>
          docs
            .map((d) => {
              const err =
                d.extracted_data &&
                typeof d.extracted_data === 'object' &&
                '_pipeline_error' in d.extracted_data
                  ? String((d.extracted_data as Record<string, unknown>)._pipeline_error)
                  : '';
              const base = `${d.document_name || d.document_id} (${normalizeDocStatus(d.status) || 'unknown'})`;
              return err ? `${base}: ${err}` : base;
            })
            .join('; ');

        const stillRunning = tracked.some(
          (doc) => !isExtractionSuccessStatus(doc.status) && !isExtractionFailedStatus(doc.status),
        );
        if (stillRunning) {
          setWorkflowHint(
            `Processing documents… (${tracked.filter((d) => isExtractionSuccessStatus(d.status)).length}/${tracked.length} ready)`,
          );
          await sleep(POLL_MS);
          continue;
        }

        // Every tracked row is terminal (done/success or failed). Merge bank payloads from successes.
        const failures = tracked.filter((doc) => isExtractionFailedStatus(doc.status));
        const successes = tracked.filter((doc) => isExtractionSuccessStatus(doc.status));
        const parsed = successes
          .map((doc) => normalizeFinancialData(doc.extracted_data))
          .filter((data): data is FinancialData => !!data);

        if (parsed.length === 0) {
          if (failures.length > 0) {
            throw new Error(
              failures.length === tracked.length
                ? `Extraction failed for: ${formatFailedDetails(failures)}`
                : `No bank-style statement could be built from successful documents. Failures: ${formatFailedDetails(failures)}`,
            );
          }
          throw new Error(
            'Extraction finished but no underwriting-compatible statement fields were returned.',
          );
        }

        if (failures.length > 0) {
          setWorkflowHint(
            `Using ${parsed.length} successful document(s); skipped ${failures.length} failed: ${formatFailedDetails(failures)}`,
          );
        } else {
          setWorkflowHint('Extraction complete (backend webhooks delivered). Building statement…');
        }
        return mergeFinancialData(parsed);
      }
      throw new Error('Timed out waiting for extraction to finish.');
    },
    [],
  );

  /**
   * Uploads to the parser API, polls until the same `document_id` rows are terminal.
   * Matches webhook/extraction completion by stable ids returned from the ingest response.
   */
  const uploadAndAwaitExtraction = useCallback(
    async (files: File[]): Promise<{ merged: FinancialData; ingest: IngestResponse }> => {
      const err = validateFilesForUpload(files);
      if (err) throw new Error(err);

      const companyId = selectedCompanyId;
      if (!companyId) throw new Error('No company selected.');

      abortRef.current = false;
      setWorkflowError(null);
      setWorkflowHint(null);
      setPhase('uploading');
      setActiveIngest(null);

      try {
        const ingest = await uploadCompanyDocuments(companyId, files);
        if (abortRef.current) throw new Error('Workflow cancelled.');

        if (ingest.company_id !== companyId) {
          throw new Error('Ingest response company_id does not match the selected company.');
        }

        if (!ingest.document_ids?.length || ingest.document_ids.length !== files.length) {
          throw new Error(
            'Server did not return one document_id per uploaded file. Restart the API server and retry.',
          );
        }

        setActiveIngest(ingest);
        setPhase('extracting');
        setWorkflowHint(
          'Queued for extraction. Polling until your document_id rows complete (same as webhook success gate).',
        );

        const merged = await waitForMatchedExtraction(ingest.case_id, ingest.document_ids, files.length);

        if (abortRef.current) throw new Error('Workflow cancelled.');

        setPhase('idle_ready_upload');
        setWorkflowHint(null);
        return { merged, ingest };
      } catch (exc) {
        setPhase(companyId ? 'idle_ready_upload' : 'pick_company');
        setWorkflowHint(null);
        setActiveIngest(null);
        throw exc;
      }
    },
    [selectedCompanyId, validateFilesForUpload, waitForMatchedExtraction],
  );

  return {
    companies,
    companiesLoading,
    companiesError,
    refreshCompanies,
    selectedCompanyId,
    selectCompany,
    phase,
    workflowError,
    workflowHint,
    setWorkflowError,
    activeIngest,
    extractionPulseStep,
    abortRef,
    validateFilesForUpload,
    uploadAndAwaitExtraction,
    resetWorkflow,
  };
}
