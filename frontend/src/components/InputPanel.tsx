import { useState, useRef, useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';
import { cn } from '@/lib/utils';
import { getPersistenceDebug } from '@/lib/api';
import { useCompanyIngestWorkflow, MAX_UPLOAD_FILES } from '@/hooks/useCompanyIngestWorkflow';
import { WorkflowStepBar, type WorkflowVisualStep } from '@/components/workflow/WorkflowStepBar';
import type { FinancialData, PersistenceDebug, CompanyCaseSummary } from '@/types';
import {
  UploadCloud,
  Play,
  RotateCcw,
  FileJson,
  FileText,
  Database,
  Building2,
  CheckCircle2,
  Link2,
  Radio,
} from 'lucide-react';
import { DocumentParseWorkflow } from '@/components/DocumentParseWorkflow';

const REGIONS = ['India', 'Philippines'];

type InputSource = 'none' | 'company_ingest';

interface InputPanelProps {
  onRun: (data: FinancialData, region: string) => void | Promise<void>;
  onReset: () => void;
  loading: boolean;
  hasResult: boolean;
}

export function InputPanel({ onRun, onReset, loading, hasResult }: InputPanelProps) {
  const wf = useCompanyIngestWorkflow();
  const { uploadAndAwaitExtraction, setWorkflowError } = wf;
  const [region, setRegion] = useState<string>('India');
  const [financialData, setFinancialData] = useState<FinancialData | null>(null);
  const [inputSource, setInputSource] = useState<InputSource>('none');
  const [fileNames, setFileNames] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parseComplete, setParseComplete] = useState(false);
  const [persistenceInfo, setPersistenceInfo] = useState<PersistenceDebug | null>(null);
  const [persistenceLoading, setPersistenceLoading] = useState(false);
  const [persistenceError, setPersistenceError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const lastAutoRunRef = useRef<string | null>(null);

  const workflowBusy = wf.phase === 'uploading' || wf.phase === 'extracting';

  const visualStep: WorkflowVisualStep = useMemo(() => {
    if (hasResult) return 'done';
    if (loading) return 'analyze';
    if (wf.phase === 'extracting' || (parseComplete && inputSource === 'company_ingest')) return 'extract';
    if (wf.phase === 'uploading') return 'upload';
    if (wf.selectedCompanyId) return 'upload';
    return 'company';
  }, [hasResult, loading, wf.phase, parseComplete, inputSource, wf.selectedCompanyId]);

  const busyStep: WorkflowVisualStep | null = loading
    ? 'analyze'
    : wf.phase === 'extracting'
      ? 'extract'
      : wf.phase === 'uploading'
        ? 'upload'
        : null;

  /** Company-scoped upload: parser API → poll by document_id → then run analysis. */
  const submitCompanyIngest = useCallback(
    async (files: File[]) => {
      setParseError(null);
      setParseComplete(false);
      setWorkflowError(null);
      setInputSource('company_ingest');
      setFileNames(files.map((f) => f.name));

      try {
        const { merged, ingest } = await uploadAndAwaitExtraction(files);
        setFinancialData(merged);
        setParseComplete(true);

        const runKey = `${ingest.case_id}:${ingest.document_ids?.join(',') ?? ''}`;
        if (lastAutoRunRef.current !== runKey) {
          lastAutoRunRef.current = runKey;
          await Promise.resolve(onRun(merged, region));
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Company ingest workflow failed.';
        setParseError(message);
        setFinancialData(null);
        setParseComplete(false);
        setInputSource('none');
      } finally {
        if (fileRef.current) fileRef.current.value = '';
      }
    },
    [uploadAndAwaitExtraction, setWorkflowError, region, onRun],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const dropped = Array.from(e.dataTransfer.files);
      if (dropped.length === 0) return;
      if (!wf.selectedCompanyId) {
        setParseError('Select a company before uploading documents.');
        return;
      }
      const combined = dropped.slice(0, MAX_UPLOAD_FILES);
      void submitCompanyIngest(combined);
    },
    [wf.selectedCompanyId, submitCompanyIngest],
  );

  function handleRunManual() {
    if (financialData) void Promise.resolve(onRun(financialData, region));
  }

  function handleReset() {
    wf.resetWorkflow();
    setFinancialData(null);
    setFileNames([]);
    setParseError(null);
    setParseComplete(false);
    setInputSource('none');
    setPersistenceInfo(null);
    setPersistenceError(null);
    lastAutoRunRef.current = null;
    onReset();
  }

  async function handleCheckPersistence() {
    setPersistenceLoading(true);
    setPersistenceError(null);
    try {
      const info = await getPersistenceDebug();
      setPersistenceInfo(info);
    } catch (err) {
      setPersistenceError(err instanceof Error ? err.message : 'Failed to fetch persistence debug data.');
      setPersistenceInfo(null);
    } finally {
      setPersistenceLoading(false);
    }
  }

  const selectedCompany: CompanyCaseSummary | undefined = useMemo(
    () => wf.companies.find((c) => c.company_id === wf.selectedCompanyId),
    [wf.companies, wf.selectedCompanyId],
  );

  return (
    <aside className="w-[min(100%,420px)] shrink-0 flex flex-col gap-4">
      <WorkflowStepBar current={visualStep} busyStep={busyStep} />

      {/* Companies */}
      <div className="rounded-xl border border-border/60 bg-elevated p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">
            1 · Company
          </p>
          {wf.companiesLoading && <Spinner className="w-3.5 h-3.5 text-muted-foreground" />}
        </div>
        {wf.companiesError && (
          <p className="text-xs text-destructive bg-destructive/5 border border-destructive/20 rounded-md px-2.5 py-1.5">
            {wf.companiesError}
          </p>
        )}
        {!wf.companiesLoading && wf.companies.length === 0 && !wf.companiesError && (
          <p className="text-xs text-muted-foreground">No companies returned from the API.</p>
        )}
        <div className="grid grid-cols-1 gap-2 max-h-[200px] overflow-y-auto pr-1">
          {wf.companies.map((c) => {
            const active = wf.selectedCompanyId === c.company_id;
            return (
              <button
                key={c.company_id}
                type="button"
                onClick={() => wf.selectCompany(c.company_id)}
                className={cn(
                  'rounded-lg border text-left px-3 py-2.5 transition-colors flex gap-2 items-start',
                  active
                    ? 'border-primary/50 bg-primary/10 ring-1 ring-primary/20'
                    : 'border-border/60 bg-background/40 hover:border-primary/30 hover:bg-muted/20',
                )}
              >
                <Building2 className={cn('w-4 h-4 shrink-0 mt-0.5', active ? 'text-primary' : 'text-muted-foreground')} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">{c.company_name}</p>
                  <p className="text-[10px] text-muted-foreground font-mono truncate">id: {c.company_id}</p>
                  {c.case_id && (
                    <p className="text-[10px] text-muted-foreground/80 font-mono truncate">case: {c.case_id}</p>
                  )}
                </div>
                {active && <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />}
              </button>
            );
          })}
        </div>
        {wf.selectedCompanyId && (
          <p className="text-[10px] text-muted-foreground flex items-center gap-1">
            <Link2 className="w-3 h-3 shrink-0" />
            Uploads are tied to <span className="font-mono text-foreground/90">{wf.selectedCompanyId}</span>
          </p>
        )}
      </div>

      {/* Region */}
      <div className="rounded-xl border border-border/60 bg-elevated p-4 space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">
          Configuration
        </p>
        <div className="space-y-1.5">
          <label className="text-xs text-muted-foreground">Underwriting region</label>
          <Select value={region} onValueChange={(v) => v && setRegion(v)}>
            <SelectTrigger className="h-9 text-sm bg-background/60 border-border/60">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {REGIONS.map((r) => (
                <SelectItem key={r} value={r} className="text-sm">
                  {r}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Upload — company scoped */}
      <div className="rounded-xl border border-border/60 bg-elevated p-4 space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">
          2 · Documents (max {MAX_UPLOAD_FILES})
        </p>
        {!wf.selectedCompanyId && (
          <p className="text-xs text-muted-foreground bg-muted/30 border border-border/50 rounded-md px-2.5 py-2">
            Select a company above to enable uploads. The parser stores a <span className="font-mono">case_id</span> and
            returns a <span className="font-mono">document_id</span> per file for extraction matching.
          </p>
        )}

        <div
          className={cn(
            'rounded-lg border-2 border-dashed p-5 flex flex-col items-center justify-center gap-2 transition-all duration-200',
            !wf.selectedCompanyId && 'opacity-50 pointer-events-none cursor-not-allowed',
            wf.selectedCompanyId && 'cursor-pointer',
            dragging ? 'border-primary bg-primary/5 scale-[0.99]' : 'border-border/50 hover:border-primary/40 hover:bg-muted/20',
            fileNames.length > 0 && inputSource === 'company_ingest' && 'border-success/40 bg-success/5',
          )}
          onDragOver={(e) => {
            e.preventDefault();
            if (wf.selectedCompanyId) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => wf.selectedCompanyId && fileRef.current?.click()}
        >
          {fileNames.length > 0 && inputSource === 'company_ingest' ? (
            <>
              {fileNames.some((name) => name.toLowerCase().endsWith('.pdf')) ? (
                <FileText className="w-8 h-8 text-success" />
              ) : (
                <FileJson className="w-8 h-8 text-success" />
              )}
              <span className="text-xs text-success font-medium text-center break-all">
                {fileNames.length === 1 ? fileNames[0] : `${fileNames.length} files`}
              </span>
            </>
          ) : (
            <>
              <UploadCloud className="w-8 h-8 text-muted-foreground/40" />
              <span className="text-xs text-muted-foreground text-center">
                Drop up to {MAX_UPLOAD_FILES} files (PDF, JSON, images, XLSX)
                <br />
                or click to upload
              </span>
            </>
          )}
          <input
            ref={fileRef}
            type="file"
            multiple
            accept=".pdf,.json,.png,.jpg,.jpeg,.xlsx,application/pdf,application/json,image/*"
            className="hidden"
            disabled={!wf.selectedCompanyId || workflowBusy || loading}
            onChange={(e) => {
              const newFiles = Array.from(e.target.files ?? []);
              if (newFiles.length > 0 && wf.selectedCompanyId) {
                void submitCompanyIngest(newFiles.slice(0, MAX_UPLOAD_FILES));
              }
            }}
          />
        </div>

        {wf.workflowHint && (
          <p className="text-[11px] text-muted-foreground border border-border/40 rounded-md px-2.5 py-2 bg-background/50 flex gap-2">
            <Radio className="w-3.5 h-3.5 shrink-0 text-primary mt-0.5" />
            <span>{wf.workflowHint}</span>
          </p>
        )}

        {wf.activeIngest && (
          <div className="rounded-md border border-border/50 bg-background/60 px-2.5 py-2 space-y-1 text-[10px] font-mono text-muted-foreground">
            <div className="flex justify-between gap-2">
              <span>case_id</span>
              <span className="text-foreground truncate max-w-[220px]">{wf.activeIngest.case_id}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span>company_id</span>
              <span className="text-foreground truncate max-w-[220px]">{wf.activeIngest.company_id}</span>
            </div>
            {wf.activeIngest.document_ids && wf.activeIngest.document_ids.length > 0 && (
              <div className="pt-1 border-t border-border/40">
                <span className="text-muted-foreground/80">document_ids</span>
                <ul className="mt-1 space-y-0.5 text-foreground/90 break-all">
                  {wf.activeIngest.document_ids.map((id) => (
                    <li key={id}>{id}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <DocumentParseWorkflow
          active={workflowBusy}
          complete={parseComplete && inputSource === 'company_ingest'}
          activeStep={wf.extractionPulseStep}
        />

        {(parseError || wf.workflowError) && (
          <p className="text-xs text-destructive bg-destructive/5 border border-destructive/20 rounded-md px-2.5 py-1.5">
            {parseError ?? wf.workflowError}
          </p>
        )}

      </div>

      {/* Actions */}
      <div className="space-y-2">
        <Button
          className="w-full gap-2 h-10"
          onClick={handleRunManual}
          disabled={!financialData || loading || workflowBusy}
        >
          {loading || workflowBusy ? (
            <>
              <Spinner className="w-4 h-4" />
              {workflowBusy ? 'Parser / extraction…' : 'Running analysis…'}
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              Re-run analysis
            </>
          )}
        </Button>
        {inputSource === 'company_ingest' && parseComplete && (
          <p className="text-[10px] text-muted-foreground text-center">
            After extraction completes, analysis starts automatically and the pipeline overlay runs.
          </p>
        )}

        {(hasResult || financialData) && (
          <Button
            variant="ghost"
            size="sm"
            className="w-full gap-2 text-muted-foreground hover:text-foreground"
            onClick={handleReset}
            disabled={loading || workflowBusy}
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset workflow
          </Button>
        )}

        <Button
          variant="outline"
          size="sm"
          className="w-full gap-2 border-border/60 text-muted-foreground hover:text-foreground hover:border-primary/40"
          onClick={handleCheckPersistence}
          disabled={loading || workflowBusy || persistenceLoading}
        >
          {persistenceLoading ? (
            <>
              <Spinner className="w-3.5 h-3.5" />
              Checking persistence…
            </>
          ) : (
            <>
              <Database className="w-3.5 h-3.5" />
              Check persistence
            </>
          )}
        </Button>
      </div>

      {persistenceError && (
        <p className="text-xs text-destructive bg-destructive/5 border border-destructive/20 rounded-md px-2.5 py-1.5">
          {persistenceError}
        </p>
      )}

      {persistenceInfo && (
        <div className="rounded-xl border border-border/60 bg-elevated p-4 space-y-2">
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60">Persistence snapshot</p>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">Cases count</span>
            <span className="text-xs font-mono text-foreground">{persistenceInfo.cases_count}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">Last case id</span>
            <span className="text-xs font-mono text-foreground">{persistenceInfo.last_case_id ?? 'N/A'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">Last case time</span>
            <span className="text-xs font-mono text-foreground">
              {persistenceInfo.last_case_timestamp
                ? new Date(persistenceInfo.last_case_timestamp).toLocaleString()
                : 'N/A'}
            </span>
          </div>
          <div className="flex justify-between border-t border-border/40 pt-2">
            <span className="text-xs text-muted-foreground">Checkpoint decision</span>
            <span className="text-xs font-mono text-foreground">
              {persistenceInfo.last_checkpoint_decision_status ?? 'N/A'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">Checkpoint risk</span>
            <span className="text-xs font-mono text-foreground">
              {persistenceInfo.last_checkpoint_risk_score ?? 'N/A'}
            </span>
          </div>
        </div>
      )}

      {financialData && (
        <div className="rounded-xl border border-border/60 bg-elevated p-4 space-y-2">
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60">Statement preview</p>
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
            {fileNames.some((name) => name.toLowerCase().endsWith('.pdf')) ? (
              <FileText className="w-3 h-3" />
            ) : (
              <FileJson className="w-3 h-3" />
            )}
            <span className="truncate">
              {selectedCompany?.company_name ? `${selectedCompany.company_name} · ` : ''}
              {fileNames.length === 0
                ? 'No file label'
                : fileNames.length === 1
                  ? fileNames[0]
                  : `${fileNames.length} files`}
            </span>
          </div>
          {financialData.applicant_id && (
            <div className="flex justify-between">
              <span className="text-xs text-muted-foreground">Applicant</span>
              <span className="text-xs font-mono text-foreground">{financialData.applicant_id}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">Inflow</span>
            <span className="text-xs font-mono text-success">+{financialData.total_inflow.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">Outflow</span>
            <span className="text-xs font-mono text-destructive">-{financialData.total_outflow.toLocaleString()}</span>
          </div>
          <div className="flex justify-between border-t border-border/40 pt-2">
            <span className="text-xs text-muted-foreground">Transactions</span>
            <span className="text-xs font-mono text-foreground">{financialData.transactions?.length ?? 0}</span>
          </div>
        </div>
      )}
    </aside>
  );
}
