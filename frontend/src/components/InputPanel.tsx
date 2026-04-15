import { useState, useRef, useCallback, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Spinner } from '@/components/ui/spinner';
import { cn } from '@/lib/utils';
import { parseDocument } from '@/lib/api';
import type { FinancialData } from '@/types';
import { UploadCloud, FlaskConical, Play, RotateCcw, FileJson, FileText } from 'lucide-react';
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
  const [fileName, setFileName] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parseStep, setParseStep] = useState(0);
  const [parseComplete, setParseComplete] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const workflowTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (workflowTimerRef.current) {
        window.clearInterval(workflowTimerRef.current);
      }
    };
  }, []);

  function normalizeFinancialData(value: unknown): FinancialData | null {
    if (!value || typeof value !== 'object') return null;
    const obj = value as Record<string, unknown>;
    if (!Array.isArray(obj.transactions)) return null;
    if (typeof obj.total_inflow !== 'number' || Number.isNaN(obj.total_inflow)) return null;
    if (typeof obj.total_outflow !== 'number' || Number.isNaN(obj.total_outflow)) return null;

    const transactions = obj.transactions
      .filter((t): t is Record<string, unknown> => !!t && typeof t === 'object')
      .map((t) => {
        const amount = typeof t.amount === 'number' ? t.amount : Number(t.amount ?? 0);
        const transactionType: 'credit' | 'debit' = t.type === 'credit' ? 'credit' : 'debit';
        return {
          date: String(t.date ?? ''),
          description: String(t.description ?? ''),
          amount: Number.isFinite(amount) ? amount : 0,
          type: transactionType,
        };
      });

    return {
      applicant_id: typeof obj.applicant_id === 'string' ? obj.applicant_id : undefined,
      statement_month: typeof obj.statement_month === 'string' ? obj.statement_month : undefined,
      transactions,
      total_inflow: obj.total_inflow,
      total_outflow: obj.total_outflow,
    };
  }

  async function parseFile(file: File) {
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
      const isJson = file.type === 'application/json' || file.name.toLowerCase().endsWith('.json');
      const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');

      if (!isJson && !isPdf) {
        setParseError('Unsupported file type. Upload a .json or .pdf statement.');
        return;
      }

      if (isPdf) {
        const parsed = await parseDocument(file.name, 'pdf');
        const normalized = normalizeFinancialData(parsed);
        if (!normalized) {
          setParseError('Unable to parse PDF into financial statement data.');
          return;
        }
        setFinancialData(normalized);
        setFileName(file.name);
        setParseStep(5);
        setParseComplete(true);
        return;
      }

      const text = await file.text();
      const raw = JSON.parse(text) as unknown;
      const normalized = normalizeFinancialData(raw);
      if (!normalized) {
        setParseError('Invalid JSON schema. Required: transactions, total_inflow, total_outflow.');
        return;
      }
      setFinancialData(normalized);
      setFileName(file.name);
      setParseStep(5);
      setParseComplete(true);
    } catch {
      setParseError('Could not read this file. Upload a valid .json or .pdf statement.');
    } finally {
      if (workflowTimerRef.current) {
        window.clearInterval(workflowTimerRef.current);
        workflowTimerRef.current = null;
      }
      setParsing(false);
    }
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      void parseFile(file);
    }
  }, []);

  async function handleUseSample() {
    setParseError(null);
    const data = await onLoadSample();
    if (data) {
      setFinancialData(data);
      setFileName('sample_statement.json');
    }
  }

  function handleRun() {
    if (financialData) onRun(financialData, region);
  }

  function handleReset() {
    setFinancialData(null);
    setFileName(null);
    setParseError(null);
    setParseStep(0);
    setParseComplete(false);
    onReset();
  }

  return (
    <aside className="w-72 shrink-0 flex flex-col gap-4">
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
            fileName && 'border-success/40 bg-success/5',
          )}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
        >
          {fileName ? (
            <>
              <FileJson className="w-8 h-8 text-success" />
              <span className="text-xs text-success font-medium text-center break-all">{fileName}</span>
            </>
          ) : (
            <>
              <UploadCloud className="w-8 h-8 text-muted-foreground/40" />
              <span className="text-xs text-muted-foreground text-center">
                Drop JSON/PDF file here<br />or click to upload
              </span>
            </>
          )}
          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json,.pdf,application/pdf"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void parseFile(f); }}
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
      </div>

      {/* Financial summary preview */}
      {financialData && (
        <div className="rounded-xl border border-border/60 bg-elevated p-4 space-y-2">
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60">Statement Preview</p>
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
            {fileName?.toLowerCase().endsWith('.pdf') ? (
              <FileText className="w-3 h-3" />
            ) : (
              <FileJson className="w-3 h-3" />
            )}
            <span className="truncate">{fileName}</span>
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
            <span className="text-xs font-mono text-foreground">{financialData.transactions.length}</span>
          </div>
        </div>
      )}
    </aside>
  );
}
