import { FileWarning, Link2 } from "lucide-react";
import { EvidenceHighlight } from "../lib/types";

interface PdfPanelProps {
  title: string;
  paperId: string;
  pdfUrl: string;
  pdfAvailable: boolean;
  highlights: EvidenceHighlight[];
  activeClaimId: string | null;
}

export function PdfPanel({ title, paperId, pdfUrl, pdfAvailable, highlights, activeClaimId }: PdfPanelProps) {
  const activeHighlight = highlights.find((highlight) => highlight.claim_id === activeClaimId) ?? null;

  return (
    <section className="surface-card flex min-h-0 flex-col p-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">PDF Renderer</p>
          <h2 className="mt-1 line-clamp-2 text-sm font-semibold text-[var(--pp-text-primary)]">{title}</h2>
          <p className="mt-0.5 text-xs text-[var(--pp-text-dim)]">{paperId}</p>
        </div>

        {activeHighlight ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2 py-1 text-xs text-[var(--pp-accent-text)]">
            <Link2 className="h-3.5 w-3.5" />
            Claim Link · p.{activeHighlight.page}
          </span>
        ) : null}
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-muted)]">
        {pdfAvailable ? (
          <>
            <iframe title="Paper PDF" src={pdfUrl} className="h-full min-h-[420px] w-full" loading="lazy" />
            {activeHighlight ? (
              <div
                className="pointer-events-none absolute border-2 border-[var(--pp-accent)] bg-[var(--pp-accent-soft)]/60"
                style={{
                  top: `${activeHighlight.top}%`,
                  left: `${activeHighlight.left}%`,
                  width: `${activeHighlight.width}%`,
                  height: `${activeHighlight.height}%`,
                }}
              />
            ) : null}
          </>
        ) : (
          <div className="flex h-full min-h-[420px] flex-col items-center justify-center gap-2 px-4 text-center">
            <FileWarning className="h-8 w-8 text-[var(--pp-text-dim)]" />
            <p className="text-sm text-[var(--pp-text-primary)]">PDF를 불러올 수 없습니다.</p>
            <p className="text-xs text-[var(--pp-text-dim)]">백엔드 PDF 엔드포인트 실패 시 mock sample PDF를 사용합니다.</p>
          </div>
        )}
      </div>
    </section>
  );
}
