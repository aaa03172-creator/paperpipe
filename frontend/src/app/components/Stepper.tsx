import { AlertCircle, CheckCircle2, Circle, LoaderCircle } from "lucide-react";
import { JobLifecycle, PipelineStage } from "../lib/types";
import { PIPELINE_STEPS } from "../lib/ui";

interface StepperProps {
  stage: PipelineStage;
  jobStatus: JobLifecycle;
}

export function Stepper({ stage, jobStatus }: StepperProps) {
  const currentIndex = PIPELINE_STEPS.findIndex((item) => item.key === stage);

  return (
    <ol className="flex flex-wrap items-center gap-2">
      {PIPELINE_STEPS.map((item, index) => {
        const isDone = index < currentIndex || (jobStatus === "completed" && index <= currentIndex);
        const isCurrent = index === currentIndex;
        const isFailed = jobStatus === "failed" && isCurrent;

        return (
          <li
            key={item.key}
            className={[
              "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs",
              isCurrent
                ? "border-[var(--pp-accent)] bg-[var(--pp-surface-selected)] text-[var(--pp-text-primary)]"
                : "border-[var(--pp-border)] bg-[var(--pp-surface-raised)] text-[var(--pp-text-dim)]",
            ].join(" ")}
          >
            {isFailed ? (
              <AlertCircle className="h-3.5 w-3.5 text-[var(--pp-status-failed-text)]" />
            ) : isDone ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-[var(--pp-status-completed-text)]" />
            ) : isCurrent && (jobStatus === "running" || jobStatus === "queued") ? (
              <LoaderCircle className="motion-safe:animate-spin h-3.5 w-3.5 text-[var(--pp-accent)]" />
            ) : (
              <Circle className="h-3.5 w-3.5" />
            )}
            <span>{item.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
