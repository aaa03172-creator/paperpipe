import { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

export function Command({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("overflow-hidden rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface)]", className)}
      {...props}
    />
  );
}

export function CommandList({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("max-h-60 overflow-auto p-1", className)} {...props} />;
}

export function CommandEmpty({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-3 py-6 text-center text-sm text-[var(--pp-text-dim)]", className)} {...props} />;
}

export function CommandGroup({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-1", className)} {...props} />;
}

export function CommandItem({
  className,
  ...props
}: HTMLAttributes<HTMLButtonElement> & { asChild?: false }) {
  return (
    <button
      type="button"
      className={cn(
        "flex w-full items-center justify-between rounded-md px-2.5 py-2 text-left text-sm text-[var(--pp-text-secondary)] transition-colors hover:bg-[var(--pp-surface-muted)] hover:text-[var(--pp-text-primary)]",
        className,
      )}
      {...props}
    />
  );
}
