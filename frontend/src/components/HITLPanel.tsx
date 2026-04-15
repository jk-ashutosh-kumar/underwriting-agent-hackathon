import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { AlertOctagon, SendHorizonal } from 'lucide-react';

interface HITLPanelProps {
  onSubmit: (response: string) => void;
  loading?: boolean;
}

export function HITLPanel({ onSubmit, loading }: HITLPanelProps) {
  const [text, setText] = useState('');

  function handleSubmit() {
    if (!text.trim()) return;
    onSubmit(text.trim());
  }

  return (
    <div className="rounded-xl border-2 border-warning/30 bg-warning/5 p-5 space-y-4">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-warning/20 border border-warning/30 flex items-center justify-center shrink-0">
          <AlertOctagon className="w-4 h-4 text-warning" />
        </div>
        <div>
          <p className="text-sm font-semibold text-warning">Human Review Required</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            A suspicious transaction was flagged. Provide clarification to resume underwriting.
          </p>
        </div>
      </div>
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Provide clarification for the flagged transaction..."
        className="bg-background/60 border-warning/20 text-sm resize-none h-24 focus-visible:ring-warning/30"
      />
      <Button
        onClick={handleSubmit}
        disabled={!text.trim() || loading}
        className="w-full bg-warning text-warning-foreground hover:bg-warning/90 gap-2"
      >
        <SendHorizonal className="w-4 h-4" />
        Submit Clarification
      </Button>
    </div>
  );
}
