import { useState, useRef, useCallback, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Spinner } from '@/components/ui/spinner';
import { cn } from '@/lib/utils';
import { getPersistenceDebug, parseDocument } from '@/lib/api';
import { normalizeFinancialData } from '@/lib/normalizeFinancialData';
import type { FinancialData, PersistenceDebug } from '@/types';
import { UploadCloud, FlaskConical, Play, RotateCcw, FileJson, FileText, Database } from 'lucide-react';
import { DocumentParseWorkflow } from '@/components/DocumentParseWorkflow';

const REGIONS = ['India', 'Philippines'];

interface InputPanelProps {
  onRun: (data: FinancialData, region: string) => void;
  onLoadSample: () => Promise<FinancialData | null>;
  onReset: () => void;
  loading: boolean;
  hasResult: boolean;
}

export function InputPanel({ onRun, onLoadSample, onReset, loading, hasResult }: InputPanelProps) {
  const [region, setRegion] = useState<string>('India');
  const [financialData, setFinancialData] = useState<FinancialData | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [fileNames, setFileNames] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parseStep, setParseStep] = useState(0);
  const [parseComplete, setParseComplete] = useState(false);
  const [persistenceInfo, setPersistenceInfo] = useState<PersistenceDebug | null>(null);
  const [persistenceLoading, setPersistenceLoading] = useState(false);
  const [persistenceError, setPersistenceError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const workflowTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (workflowTimerRef.current) {
        window.clearInterval(workflowTimerRef.current);
      }
    };
  }, []);

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

  async function parseSingleFile(file: File): Promise<FinancialData | null> {
    const isJson = file.type === 'application/json' || file.name.toLowerCase().endsWith('.json');
    const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');

    if (!isJson && !isPdf) {
      throw new Error('Unsupported file type. Upload a .json or .pdf statement.');
    }

    if (isPdf) {
      const parsed = await parseDocument(file.name, 'pdf');
      return normalizeFinancialData(parsed);
    }

    const text = await file.text();
    const raw = JSON.parse(text) as unknown;
    return normalizeFinancialData(raw);
  }

  async function parseFiles(files: File[]) {
    if (files.length === 0) return;
    
    setParseError(null);
    setParsing(true);
    setParseStep(0);
    setParseComplete(false);
    if (workflowTimerRef.current) {
      window.clearInterval(workflowTimerRef.current);
    }

    workflowTimerRef.current = window.setInterval(() => {
      setParseStep((prev) => (prev < 5 ? prev + 1 : prev));
    }, 450);

    try {
      if (files.length > 2) {
        setParseError('You can upload at most 2 files at once.');
        return;
      }

      const parsedData: FinancialData[] = [];
      for (const file of files) {
        const normalized = await parseSingleFile(file);
        if (!normalized) {
          setParseError(`Could not parse ${file.name}. Check file schema/content and retry.`);
          return;
        }
        parsedData.push(normalized);
      }

      setFinancialData(mergeFinancialData(parsedData));
      setFileNames(files.map((f) => f.name));
      setSelectedFiles(files);
      setParseStep(5);
      setParseComplete(true);
    } catch {
      setParseError('Could not read selected files. Upload valid .json/.pdf files (max 2).');
    } finally {
      if (workflowTimerRef.current) {
        window.clearInterval(workflowTimerRef.current);
        workflowTimerRef.current = null;
      }
      setParsing(false);
      // Reset input value so same file can be selected again if purged
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      const combined = [...selectedFiles, ...droppedFiles].slice(0, 2);
      void parseFiles(combined);
    }
  }, [selectedFiles]);

  async function handleUseSample() {
    setParseError(null);
    const data = await onLoadSample();
    if (data) {
      setFinancialData(data);
      setFileNames(['sample_statement.json']);
      setSelectedFiles([]); // Sample data doesn't have real File objects
    }
  }

  function handleRun() {
    if (financialData) onRun(financialData, region);
  }

  function handleReset() {
    setFinancialData(null);
    setFileNames([]);
    setSelectedFiles([]);
    setParseError(null);
    setParseStep(0);
    setParseComplete(false);
    setPersistenceInfo(null);
    setPersistenceError(null);
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

  return (
    <aside className="w-64 shrink-0 flex flex-col gap-4">
      {/* Region */}
      <div className="rounded-xl border border-border/60 bg-elevated p-4 space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">
          Configuration
        </p>
        <div className="space-y-1.5">
          <label className="text-xs text-muted-foreground">Select Region</label>
          <Select value={region} onValueChange={(v) => v && setRegion(v)}>
            <SelectTrigger className="h-9 text-sm bg-background/60 border-border/60">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {REGIONS.map((r) => (
                <SelectItem key={r} value={r} className="text-sm">{r}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Upload */}
      <div className="rounded-xl border border-border/60 bg-elevated p-4 space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">
          Statement Input
        </p>

        {/* Drop Zone */}
        <div
          className={cn(
            'rounded-lg border-2 border-dashed p-5 flex flex-col items-center justify-center gap-2 cursor-pointer transition-all duration-200',
            dragging ? 'border-primary bg-primary/5 scale-[0.99]' : 'border-border/50 hover:border-primary/40 hover:bg-muted/20',
            fileNames.length > 0 && 'border-success/40 bg-success/5',
          )}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
        >
          {fileNames.length > 0 ? (
            <>
              {fileNames.some((name) => name.toLowerCase().endsWith('.pdf')) ? (
                <FileText className="w-8 h-8 text-success" />
              ) : (
                <FileJson className="w-8 h-8 text-success" />
              )}
              <span className="text-xs text-success font-medium text-center break-all">
                {fileNames.length === 1 ? fileNames[0] : `${fileNames.length} files selected`}
              </span>
            </>
          ) : (
            <>
              <UploadCloud className="w-8 h-8 text-muted-foreground/40" />
              <span className="text-xs text-muted-foreground text-center">
                Drop up to 2 JSON/PDF files here<br />or click to upload
              </span>
            </>
          )}
          <input
            ref={fileRef}
            type="file"
            multiple
            accept=".json,application/json,.pdf,application/pdf"
            className="hidden"
            onChange={(e) => {
              const newFiles = Array.from(e.target.files ?? []);
              if (newFiles.length > 0) {
                const combined = [...selectedFiles, ...newFiles].slice(0, 2);
                void parseFiles(combined);
              }
            }}
          />
        </div>

        <DocumentParseWorkflow active={parsing} complete={parseComplete} activeStep={parseStep} />

        {parseError && (
          <p className="text-xs text-destructive bg-destructive/5 border border-destructive/20 rounded-md px-2.5 py-1.5">
            {parseError}
          </p>
        )}

        <div className="flex items-center gap-2">
          <Separator className="flex-1 bg-border/40" />
          <span className="text-[10px] text-muted-foreground/40 uppercase tracking-widest">or</span>
          <Separator className="flex-1 bg-border/40" />
        </div>

        <Button
          variant="outline"
          size="sm"
          className="w-full gap-2 border-border/60 text-muted-foreground hover:text-foreground hover:border-primary/40"
          onClick={handleUseSample}
          disabled={loading}
        >
          <FlaskConical className="w-3.5 h-3.5" />
          Use Sample Data
        </Button>
      </div>

      {/* Actions */}
      <div className="space-y-2">
        <Button
          className="w-full gap-2 h-10"
          onClick={handleRun}
          disabled={!financialData || loading || parsing}
        >
          {loading || parsing ? (
            <>
              <Spinner className="w-4 h-4" />
              {parsing ? 'Parsing statement...' : 'Running Agent Committee...'}
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              Run Analysis
            </>
          )}
        </Button>

        {(hasResult || financialData) && (
          <Button
            variant="ghost"
            size="sm"
            className="w-full gap-2 text-muted-foreground hover:text-foreground"
            onClick={handleReset}
            disabled={loading || parsing}
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset
          </Button>
        )}

        <Button
          variant="outline"
          size="sm"
          className="w-full gap-2 border-border/60 text-muted-foreground hover:text-foreground hover:border-primary/40"
          onClick={handleCheckPersistence}
          disabled={loading || parsing || persistenceLoading}
        >
          {persistenceLoading ? (
            <>
              <Spinner className="w-3.5 h-3.5" />
              Checking Persistence...
            </>
          ) : (
            <>
              <Database className="w-3.5 h-3.5" />
              Check Persistence
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
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60">Persistence Snapshot</p>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">Cases Count</span>
            <span className="text-xs font-mono text-foreground">{persistenceInfo.cases_count}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">Last Case ID</span>
            <span className="text-xs font-mono text-foreground">{persistenceInfo.last_case_id ?? 'N/A'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">Last Case Time</span>
            <span className="text-xs font-mono text-foreground">
              {persistenceInfo.last_case_timestamp ? new Date(persistenceInfo.last_case_timestamp).toLocaleString() : 'N/A'}
            </span>
          </div>
          <div className="flex justify-between border-t border-border/40 pt-2">
            <span className="text-xs text-muted-foreground">Checkpoint Decision</span>
            <span className="text-xs font-mono text-foreground">
              {persistenceInfo.last_checkpoint_decision_status ?? 'N/A'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">Checkpoint Risk</span>
            <span className="text-xs font-mono text-foreground">
              {persistenceInfo.last_checkpoint_risk_score ?? 'N/A'}
            </span>
          </div>
        </div>
      )}

      {/* Financial summary preview */}
      {financialData && (
        <div className="rounded-xl border border-border/60 bg-elevated p-4 space-y-2">
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60">Statement Preview</p>
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
            {fileNames.some((name) => name.toLowerCase().endsWith('.pdf')) ? (
              <FileText className="w-3 h-3" />
            ) : (
              <FileJson className="w-3 h-3" />
            )}
            <span className="truncate">
              {fileNames.length === 0
                ? 'No file selected'
                : fileNames.length === 1
                  ? fileNames[0]
                  : `${fileNames.length} files merged`}
            </span>
          </div>
          {fileNames.length > 1 && (
            <div className="flex flex-wrap gap-1.5">
              {fileNames.map((name) => (
                <span
                  key={name}
                  className="text-[10px] px-1.5 py-1 rounded border border-border/50 bg-background/70 text-muted-foreground"
                >
                  {name}
                </span>
              ))}
            </div>
          )}
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
