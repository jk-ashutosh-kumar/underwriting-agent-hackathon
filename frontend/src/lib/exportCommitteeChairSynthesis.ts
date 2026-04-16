import type { CommitteeChairResult, UnderwritingResult } from '@/types';

export type CommitteeChairSynthesisExport = {
  exported_at: string;
  title: string;
  confidence_percent: number;
  final_verdict_rationale: string;
  key_supporting_points: string[];
  key_risks: string[];
  conditions_if_approved: string[];
  mode?: CommitteeChairResult['mode'];
  llm_error?: string | null;
};

function safeChair(result: UnderwritingResult): CommitteeChairResult | undefined {
  return result.committee_chair;
}

export function buildCommitteeChairSynthesisExport(result: UnderwritingResult): CommitteeChairSynthesisExport {
  const c = safeChair(result);
  return {
    exported_at: new Date().toISOString(),
    title: 'Committee Chair Synthesis',
    confidence_percent: c?.confidence ?? 0,
    final_verdict_rationale: (c?.final_verdict_rationale ?? '').trim(),
    key_supporting_points: [...(c?.key_supporting_points ?? [])],
    key_risks: [...(c?.key_risks ?? [])],
    conditions_if_approved: [...(c?.conditions_if_approved ?? [])],
    mode: c?.mode,
    llm_error: c?.llm_error ?? null,
  };
}

export function hasCommitteeChairExportData(result: UnderwritingResult): boolean {
  const c = safeChair(result);
  if (!c) return false;
  if (c.final_verdict_rationale?.trim()) return true;
  if (c.key_supporting_points?.some((s) => String(s).trim())) return true;
  if (c.key_risks?.some((s) => String(s).trim())) return true;
  if ((c.conditions_if_approved?.length ?? 0) > 0) return true;
  if ((c.confidence ?? 0) > 0) return true;
  if (c.llm_error) return true;
  return false;
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = 'noopener';
  anchor.click();
  URL.revokeObjectURL(url);
}

export function downloadCommitteeChairSynthesisJson(result: UnderwritingResult): void {
  const payload = buildCommitteeChairSynthesisExport(result);
  const body = JSON.stringify(payload, null, 2);
  const blob = new Blob([body], { type: 'application/json;charset=utf-8' });
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
  triggerBlobDownload(blob, `committee-chair-synthesis-${stamp}.json`);
}

function writeLines(
  doc: import('jspdf').jsPDF,
  lines: string[],
  x: number,
  yStart: number,
  lineHeight: number,
  margin: number,
): number {
  const pageHeight = doc.internal.pageSize.getHeight();
  const bottom = pageHeight - margin;
  let y = yStart;
  for (const line of lines) {
    if (y > bottom - lineHeight) {
      doc.addPage();
      y = margin;
    }
    doc.text(line, x, y);
    y += lineHeight;
  }
  return y;
}

function writeParagraph(
  doc: import('jspdf').jsPDF,
  text: string,
  x: number,
  yStart: number,
  maxWidth: number,
  lineHeight: number,
  margin: number,
): number {
  if (!text.trim()) return yStart;
  const wrapped = doc.splitTextToSize(text, maxWidth);
  return writeLines(doc, wrapped, x, yStart, lineHeight, margin);
}

function writeHeading(doc: import('jspdf').jsPDF, title: string, x: number, y: number, margin: number): number {
  const pageHeight = doc.internal.pageSize.getHeight();
  const lineH = 6;
  let cursorY = y;
  if (cursorY > pageHeight - margin - lineH) {
    doc.addPage();
    cursorY = margin;
  }
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(11);
  doc.text(title, x, cursorY);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  return cursorY + lineH;
}

function writeBulletList(
  doc: import('jspdf').jsPDF,
  items: string[],
  x: number,
  yStart: number,
  maxWidth: number,
  lineHeight: number,
  margin: number,
): number {
  let y = yStart;
  const usable = items.filter((s) => String(s).trim());
  if (usable.length === 0) {
    return writeParagraph(doc, '— None listed.', x, y, maxWidth, lineHeight, margin);
  }
  for (const item of usable) {
    const block = `• ${item}`;
    y = writeParagraph(doc, block, x, y, maxWidth - 4, lineHeight, margin);
    y += 2;
  }
  return y;
}

export async function downloadCommitteeChairSynthesisPdf(result: UnderwritingResult): Promise<void> {
  const { jsPDF } = await import('jspdf');
  const data = buildCommitteeChairSynthesisExport(result);
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const margin = 16;
  const pageWidth = doc.internal.pageSize.getWidth();
  const maxWidth = pageWidth - margin * 2;
  const lineHeight = 5;

  let y = margin;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.text(data.title, margin, y);
  y += 10;

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  y = writeParagraph(
    doc,
    `Exported: ${new Date(data.exported_at).toLocaleString()}\nConfidence: ${data.confidence_percent}%`,
    margin,
    y,
    maxWidth,
    lineHeight,
    margin,
  );
  y += 4;

  y = writeHeading(doc, 'Final verdict rationale', margin, y + 4, margin);
  y = writeParagraph(doc, data.final_verdict_rationale || '— Not provided.', margin, y, maxWidth, lineHeight, margin);
  y += 6;

  y = writeHeading(doc, 'Key supporting points', margin, y, margin);
  y = writeBulletList(doc, data.key_supporting_points, margin, y, maxWidth, lineHeight, margin);
  y += 4;

  y = writeHeading(doc, 'Key risks', margin, y, margin);
  y = writeBulletList(doc, data.key_risks, margin, y, maxWidth, lineHeight, margin);
  y += 4;

  y = writeHeading(doc, 'Conditions if approved', margin, y, margin);
  y = writeBulletList(doc, data.conditions_if_approved, margin, y, maxWidth, lineHeight, margin);

  if (data.mode || data.llm_error) {
    y += 6;
    y = writeHeading(doc, 'Metadata', margin, y, margin);
    const metaBits = [`Mode: ${data.mode ?? '—'}`];
    if (data.llm_error) metaBits.push(`LLM error: ${data.llm_error}`);
    y = writeParagraph(doc, metaBits.join('\n'), margin, y, maxWidth, lineHeight, margin);
  }

  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
  doc.save(`committee-chair-synthesis-${stamp}.pdf`);
}
