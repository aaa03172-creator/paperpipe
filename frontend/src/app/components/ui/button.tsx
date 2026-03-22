import { ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "../../lib/cn";

type ButtonVariant = "default" | "outline" | "ghost" | "secondary";
type ButtonSize = "default" | "sm" | "icon";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const variantClassName: Record<ButtonVariant, string> = {
  default: "border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] text-[var(--pp-accent-text)] hover:opacity-90",
  outline: "border-[var(--pp-border)] bg-[var(--pp-surface-raised)] text-[var(--pp-text-secondary)] hover:text-[var(--pp-text-primary)]",
  ghost: "border-transparent bg-transparent text-[var(--pp-text-secondary)] hover:bg-[var(--pp-surface-muted)] hover:text-[var(--pp-text-primary)]",
  secondary: "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-primary)] hover:bg-[var(--pp-surface-raised)]",
};

const sizeClassName: Record<ButtonSize, string> = {
  default: "h-10 px-4 py-2 text-sm",
  sm: "h-8 px-3 py-1.5 text-xs",
  icon: "h-10 w-10 p-0",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "default", size = "default", type = "button", ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        variantClassName[variant],
        sizeClassName[size],
        className,
      )}
      {...props}
    />
  );
});
