import { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

export function Separator({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden="true" className={cn("h-px w-full bg-[var(--pp-border)]", className)} {...props} />;
}
