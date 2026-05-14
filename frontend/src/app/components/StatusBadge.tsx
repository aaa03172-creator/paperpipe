import { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleDashed, LoaderCircle } from "lucide-react";
import { cn } from "../lib/cn";
import { StatusTone, getStatusToneClassName } from "../lib/statusSystem";
import { Badge } from "./ui/badge";

type StatusIconTone = Extract<StatusTone, "idle" | "processing" | "success" | "warning" | "danger">;

interface StatusBadgeProps {
  label: string;
  tone: StatusTone;
  iconTone?: StatusIconTone | null;
  className?: string;
  testId?: string;
}

function iconForTone(tone: StatusIconTone): ReactNode {
  if (tone === "processing") {
    return <LoaderCircle className="h-3.5 w-3.5 motion-safe:animate-spin" />;
  }
  if (tone === "success") {
    return <CheckCircle2 className="h-3.5 w-3.5" />;
  }
  if (tone === "warning" || tone === "danger") {
    return <AlertTriangle className="h-3.5 w-3.5" />;
  }
  return <CircleDashed className="h-3.5 w-3.5" />;
}

export function StatusBadge({ label, tone, iconTone = null, className, testId }: StatusBadgeProps) {
  return (
    <Badge
      data-testid={testId}
      className={cn("gap-1", getStatusToneClassName(tone), className)}
    >
      {iconTone ? iconForTone(iconTone) : null}
      {label}
    </Badge>
  );
}
