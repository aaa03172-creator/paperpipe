import { JobLifecycle, PaperUiStatus } from "../lib/types";
import { jobLabel, statusLabel } from "../lib/ui";
import { getPaperLifecycleTone } from "../lib/statusSystem";
import { StatusBadge } from "./StatusBadge";

interface StatusChipProps {
  status: PaperUiStatus | JobLifecycle;
  asJob?: boolean;
}

export function StatusChip({ status, asJob = false }: StatusChipProps) {
  const normalized = String(status).toLowerCase();
  const tone = getPaperLifecycleTone(normalized as PaperUiStatus | JobLifecycle);
  const iconTone =
    tone === "idle" || tone === "processing" || tone === "success" || tone === "warning" || tone === "danger"
      ? tone
      : null;
  return (
    <StatusBadge
      label={asJob ? jobLabel(status as JobLifecycle) : statusLabel(status as PaperUiStatus)}
      tone={tone}
      iconTone={iconTone}
    />
  );
}
