import { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type BadgeVariant = "default" | "outline" | "muted";

const variantClassName: Record<BadgeVariant, string> = {
  default: "border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] text-[var(--pp-accent-text)]",
  outline: "border-[var(--pp-border)] bg-[var(--pp-surface-raised)] text-[var(--pp-text-secondary)]",
  muted: "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-secondary)]",
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
        variantClassName[variant],
        className,
      )}
      {...props}
    />
  );
}
