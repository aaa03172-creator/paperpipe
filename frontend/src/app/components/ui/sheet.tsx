import { ReactNode, useEffect } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "../../lib/cn";
import { Button } from "./button";

interface SheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
}

export function Sheet({ open, onOpenChange, title, description, children }: SheetProps) {
  useEffect(() => {
    if (!open) {
      return;
    }
    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onOpenChange(false);
      }
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeydown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeydown);
    };
  }, [open, onOpenChange]);

  if (!open || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div className="fixed inset-0 z-50 md:hidden">
      <button
        type="button"
        aria-label="Close side panel"
        className="absolute inset-0 bg-black/60"
        onClick={() => onOpenChange(false)}
      />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="paper-note-sheet-title"
        className={cn(
          "absolute inset-y-0 right-0 flex w-[min(92vw,26rem)] flex-col border-l border-[var(--pp-border)] bg-[var(--pp-canvas)] shadow-2xl",
        )}
        data-testid="paper-note-sheet"
      >
        <header className="flex items-start justify-between gap-3 border-b border-[var(--pp-border)] px-4 py-4">
          <div>
            <h2 id="paper-note-sheet-title" className="text-base font-semibold text-[var(--pp-text-primary)]">
              {title}
            </h2>
            {description ? <p className="mt-1 text-sm text-[var(--pp-text-secondary)]">{description}</p> : null}
          </div>
          <Button variant="ghost" size="icon" onClick={() => onOpenChange(false)} aria-label="Close side panel">
            <X className="h-4 w-4" />
          </Button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">{children}</div>
      </section>
    </div>,
    document.body,
  );
}
