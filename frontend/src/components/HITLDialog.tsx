import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, X, Send, Calendar, Tag, FileText } from 'lucide-react';

export interface HITLContext {
  message: string;
  transaction?: {
    amount?: number;
    date?: string;
    type?: string;
    description?: string;
  };
}

interface HITLDialogProps {
  context: HITLContext | null;
  onSubmit: (clarification: string) => void;
  onCancel: () => void;
}

export function HITLDialog({ context, onSubmit, onCancel }: HITLDialogProps) {
  const [text, setText] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const tx = context?.transaction;

  function handleSubmit() {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
  }

  return (
    <AnimatePresence>
      {context && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />

          {/* Dialog */}
          <motion.div
            className="fixed inset-0 z-[70] flex items-center justify-center p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="relative w-full max-w-lg bg-card border border-border/60 rounded-2xl shadow-2xl overflow-hidden"
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
              transition={{ type: 'spring', damping: 22, stiffness: 300 }}
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-4 p-6 border-b border-border/40 bg-warning/[0.05]">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-warning/10 border border-warning/20">
                    <AlertTriangle className="w-5 h-5 text-warning" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-foreground">Human Review Required</h2>
                    <p className="text-xs text-muted-foreground mt-0.5">A flagged transaction needs your input to continue</p>
                  </div>
                </div>
                <button
                  onClick={onCancel}
                  className="p-1.5 rounded-lg hover:bg-muted/60 transition-colors text-muted-foreground hover:text-foreground"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Alert message */}
              <div className="px-6 pt-5">
                <div className="p-3 rounded-xl bg-warning/5 border border-warning/15 text-sm text-warning leading-relaxed">
                  {context.message}
                </div>
              </div>

              {/* Transaction details */}
              {tx && (
                <div className="px-6 pt-4">
                  <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-semibold mb-3">
                    Flagged Transaction Details
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    {tx.date && (
                      <div className="flex items-center gap-2 p-2.5 rounded-lg bg-muted/20 border border-border/30">
                        <Calendar className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                        <div>
                          <p className="text-[9px] text-muted-foreground/60 uppercase tracking-wider">Date</p>
                          <p className="text-xs font-mono font-medium text-foreground">{tx.date}</p>
                        </div>
                      </div>
                    )}
                    {tx.amount != null && (
                      <div className="flex items-center gap-2 p-2.5 rounded-lg bg-muted/20 border border-border/30">
                        {/* <DollarSign className="w-3.5 h-3.5 text-muted-foreground shrink-0" /> */}
                        <div>
                          <p className="text-[9px] text-muted-foreground/60 uppercase tracking-wider">Amount</p>
                          <p className="text-xs font-mono font-medium text-foreground">{tx.amount.toLocaleString()}</p>
                        </div>
                      </div>
                    )}
                    {tx.type && (
                      <div className="flex items-center gap-2 p-2.5 rounded-lg bg-muted/20 border border-border/30">
                        <Tag className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                        <div>
                          <p className="text-[9px] text-muted-foreground/60 uppercase tracking-wider">Type</p>
                          <p className="text-xs font-mono font-medium text-foreground capitalize">{tx.type}</p>
                        </div>
                      </div>
                    )}
                    {tx.description && (
                      <div className="flex items-center gap-2 p-2.5 rounded-lg bg-muted/20 border border-border/30 col-span-2">
                        <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                        <div>
                          <p className="text-[9px] text-muted-foreground/60 uppercase tracking-wider">Description</p>
                          <p className="text-xs font-mono font-medium text-foreground">{tx.description}</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Input */}
              <div className="px-6 pt-4 pb-6">
                <label className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60 block mb-2">
                  Your Clarification
                </label>
                <textarea
                  ref={inputRef}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Explain this flagged transaction or provide context for the underwriting team..."
                  className="w-full min-h-[84px] px-3 py-2.5 text-sm bg-muted/20 border border-border/50 rounded-xl resize-none outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/20 transition-all text-foreground placeholder:text-muted-foreground/40"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit();
                  }}
                />
                {/* <p className="text-[10px] text-muted-foreground/40 mt-1.5">Press Ctrl+Enter to submit</p> */}

                <div className="flex items-center justify-end gap-3 mt-4">
                  <button
                    onClick={onCancel}
                    className="px-4 py-2 text-sm rounded-xl border border-border/50 text-muted-foreground hover:bg-muted/30 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSubmit}
                    disabled={!text.trim()}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                  >
                    <Send className="w-3.5 h-3.5" />
                    Submit Clarification
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
