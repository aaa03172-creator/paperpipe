interface ArtifactHeaderContextItem {
  label: string;
  value: string;
}

interface ArtifactHeaderContextProps {
  items: ArtifactHeaderContextItem[];
  testId?: string;
}

export function ArtifactHeaderContext({ items, testId }: ArtifactHeaderContextProps) {
  const visibleItems = items.filter((item) => item.value.trim().length > 0);
  if (visibleItems.length === 0) {
    return null;
  }

  return (
    <div data-testid={testId} className="mt-3 grid gap-2 md:grid-cols-2">
      {visibleItems.map((item) => (
        <div
          key={item.label}
          className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2"
        >
          <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
            {item.label}
          </div>
          <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">{item.value}</p>
        </div>
      ))}
    </div>
  );
}
