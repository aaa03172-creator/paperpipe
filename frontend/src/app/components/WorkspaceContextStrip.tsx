import { ReactNode } from "react";

interface WorkspaceContextStripProps {
  title?: string;
  description: string;
  children: ReactNode;
  testId?: string;
  className?: string;
}

interface WorkspaceContextCardProps {
  eyebrow: string;
  children: ReactNode;
  testId?: string;
  className?: string;
}

export function WorkspaceContextStrip({
  title = "Workspace context",
  description,
  children,
  testId,
  className,
}: WorkspaceContextStripProps) {
  return (
    <div
      data-testid={testId}
      className={["mt-4 rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3", className ?? ""].join(" ").trim()}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">{title}</p>
      <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">{description}</p>
      <div className="mt-3 grid gap-2 lg:grid-cols-3">{children}</div>
    </div>
  );
}

export function WorkspaceContextCard({ eyebrow, children, testId, className }: WorkspaceContextCardProps) {
  return (
    <div
      data-testid={testId}
      className={["rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)] px-3 py-2", className ?? ""].join(" ").trim()}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--pp-text-dim)]">{eyebrow}</p>
      <div className="mt-2 grid gap-1.5">{children}</div>
    </div>
  );
}
