interface ArtifactHeaderContextItem {
  label: string;
  value: string;
}

interface ArtifactHeaderContextProps {
  items: ArtifactHeaderContextItem[];
  testId?: string;
  emphasizeFirstItem?: boolean;
}

export function ArtifactHeaderContext({ items, testId, emphasizeFirstItem = false }: ArtifactHeaderContextProps) {
  const visibleItems = items.filter((item) => item.value.trim().length > 0);
  if (visibleItems.length === 0) {
    return null;
  }

  return (
    <div data-testid={testId} className="mt-3 grid gap-2 md:grid-cols-2">
      {visibleItems.map((item, index) => {
        const emphasized = emphasizeFirstItem && index === 0;
        return (
        <div
          key={item.label}
          className={[
            "rounded-md border px-3 py-2",
            emphasized
              ? "border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] md:col-span-2"
              : "border-[var(--pp-border)] bg-[var(--pp-surface-raised)]",
          ].join(" ")}
        >
          <div
            className={[
              "text-[11px] font-semibold uppercase tracking-wide",
              emphasized ? "text-[var(--pp-accent-text)]" : "text-[var(--pp-text-dim)]",
            ].join(" ")}
          >
            {item.label}
          </div>
          <p className={["mt-1 text-sm", emphasized ? "text-[var(--pp-accent-text)]" : "text-[var(--pp-text-secondary)]"].join(" ")}>
            {item.value}
          </p>
        </div>
        );
      })}
    </div>
  );
}
