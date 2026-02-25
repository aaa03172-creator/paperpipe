import { AlertTriangle, CircleDotDashed, Clock3, Info } from "lucide-react";
import { TimelineEvent } from "../lib/types";

interface TimelinePanelProps {
  events: TimelineEvent[];
}

function eventIcon(event: TimelineEvent) {
  if (event.event === "error") {
    return <AlertTriangle className="h-3.5 w-3.5 text-[var(--pp-status-failed-text)]" />;
  }
  if (event.event === "done") {
    return <CircleDotDashed className="h-3.5 w-3.5 text-[var(--pp-status-completed-text)]" />;
  }
  return <Info className="h-3.5 w-3.5 text-[var(--pp-text-dim)]" />;
}

export function TimelinePanel({ events }: TimelinePanelProps) {
  return (
    <section className="surface-card flex min-h-[220px] flex-col p-3">
      <header className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
        <Clock3 className="h-3.5 w-3.5" />
        Timeline
      </header>

      <ul className="space-y-2 overflow-auto pr-1 text-sm">
        {events.length > 0 ? (
          events.map((event, index) => (
            <li key={`${event.ts ?? "evt"}-${index}`} className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-2.5">
              <div className="flex items-start gap-2">
                <span className="mt-0.5">{eventIcon(event)}</span>
                <div>
                  <p className="text-xs text-[var(--pp-text-dim)]">{event.ts ? new Date(event.ts).toLocaleTimeString() : "-"}</p>
                  <p className="text-sm text-[var(--pp-text-primary)]">{event.message ?? event.raw ?? event.event}</p>
                  {event.stage ? <p className="text-xs text-[var(--pp-text-dim)]">stage: {event.stage}</p> : null}
                </div>
              </div>
            </li>
          ))
        ) : (
          <li className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-dim)]">
            Timeline events will appear after a run starts.
          </li>
        )}
      </ul>
    </section>
  );
}
