import { ReactNode, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleDotDashed, Clock3, Info } from "lucide-react";
import { TimelineEvent } from "../lib/types";

interface TimelinePanelProps {
  events: TimelineEvent[];
  density: "detail" | "compact";
}

type TimelineFilter = "all" | "status" | "error" | "done";

function eventMessage(event: TimelineEvent): string {
  return event.message ?? event.raw ?? event.event;
}

function eventMeta(event: TimelineEvent): {
  badge: string;
  icon: ReactNode;
  badgeClass: string;
  cardClass: string;
} {
  if (event.event === "error") {
    return {
      badge: "ERROR",
      icon: <AlertTriangle className="h-3.5 w-3.5 text-[var(--pp-status-failed-text)]" />,
      badgeClass: "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]",
      cardClass: "border-[var(--pp-status-failed-border)]",
    };
  }
  if (event.event === "done") {
    return {
      badge: "DONE",
      icon: <CheckCircle2 className="h-3.5 w-3.5 text-[var(--pp-status-completed-text)]" />,
      badgeClass: "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]",
      cardClass: "border-[var(--pp-status-completed-border)]",
    };
  }
  if (event.event === "status") {
    return {
      badge: "STATUS",
      icon: <CircleDotDashed className="h-3.5 w-3.5 text-[var(--pp-accent-text)]" />,
      badgeClass: "border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] text-[var(--pp-accent-text)]",
      cardClass: "border-[var(--pp-accent-border)]",
    };
  }
  return {
    badge: "LOG",
    icon: <Info className="h-3.5 w-3.5 text-[var(--pp-text-dim)]" />,
    badgeClass: "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-dim)]",
    cardClass: "border-[var(--pp-border)]",
  };
}

export function TimelinePanel({ events, density }: TimelinePanelProps) {
  const [filter, setFilter] = useState<TimelineFilter>("status");
  const compact = density === "compact";
  const newestFirst = [...events].reverse();
  const latestEvent = newestFirst[0] ?? null;
  const latestError = newestFirst.find((event) => event.event === "error") ?? null;
  const latestDone = newestFirst.find((event) => event.event === "done") ?? null;
  const latestStatus = newestFirst.find((event) => event.event === "status") ?? null;
  const lastStage = latestStatus?.stage ?? latestEvent?.stage ?? "-";
  const errorCount = events.filter((event) => event.event === "error").length;
  const doneCount = events.filter((event) => event.event === "done").length;
  const statusCount = events.filter((event) => event.event === "status").length;
  const effectiveFilter: TimelineFilter =
    filter === "status" && events.length > 0 && statusCount === 0 ? "all" : filter;

  const filteredEvents =
    effectiveFilter === "all"
      ? newestFirst
      : effectiveFilter === "error"
        ? newestFirst.filter((event) => event.event === "error")
        : effectiveFilter === "done"
          ? newestFirst.filter((event) => event.event === "done")
          : newestFirst.filter((event) => event.event === "status");
  const renderedEvents = compact ? filteredEvents.slice(0, 8) : filteredEvents;

  return (
    <section className="surface-card flex min-h-[220px] max-h-[68vh] flex-col overflow-hidden p-3 xl:max-h-[calc(100vh-7rem)]">
      <header className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">
        <Clock3 className="h-3.5 w-3.5" />
        Timeline
      </header>

      {events.length > 0 && !compact ? (
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => setFilter("all")}
            className={[
              "rounded-full border px-2 py-0.5 text-[11px]",
              effectiveFilter === "all"
                ? "border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] text-[var(--pp-accent-text)]"
                : "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-dim)]",
            ].join(" ")}
          >
            All ({events.length})
          </button>
          <button
            type="button"
            onClick={() => setFilter("status")}
            className={[
              "rounded-full border px-2 py-0.5 text-[11px]",
              effectiveFilter === "status"
                ? "border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] text-[var(--pp-accent-text)]"
                : "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-dim)]",
            ].join(" ")}
          >
            Status ({statusCount})
          </button>
          <button
            type="button"
            onClick={() => setFilter("error")}
            className={[
              "rounded-full border px-2 py-0.5 text-[11px]",
              effectiveFilter === "error"
                ? "border-[var(--pp-status-failed-border)] bg-[var(--pp-status-failed-bg)] text-[var(--pp-status-failed-text)]"
                : "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-dim)]",
            ].join(" ")}
          >
            Error ({errorCount})
          </button>
          <button
            type="button"
            onClick={() => setFilter("done")}
            className={[
              "rounded-full border px-2 py-0.5 text-[11px]",
              effectiveFilter === "done"
                ? "border-[var(--pp-status-completed-border)] bg-[var(--pp-status-completed-bg)] text-[var(--pp-status-completed-text)]"
                : "border-[var(--pp-border)] bg-[var(--pp-surface-muted)] text-[var(--pp-text-dim)]",
            ].join(" ")}
          >
            Done ({doneCount})
          </button>
        </div>
      ) : null}

      {events.length > 0 ? (
        <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
          <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-2.5">
            <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Latest</p>
            <p className="mt-1 line-clamp-2 text-xs text-[var(--pp-text-primary)]">{latestEvent ? eventMessage(latestEvent) : "-"}</p>
          </article>
          <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-2.5">
            <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Errors / Done</p>
            <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{errorCount} / {doneCount}</p>
          </article>
          <article className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-2.5">
            <p className="text-[11px] uppercase tracking-wide text-[var(--pp-text-dim)]">Last Stage</p>
            <p className="mt-1 text-sm font-semibold text-[var(--pp-text-primary)]">{lastStage}</p>
          </article>
        </div>
      ) : null}

      {events.length > 0 ? (
        <div className="mb-3 space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Pinned Events</p>
          <ul className="space-y-1">
            {(latestError || latestDone || latestStatus) && (
              <>
                {latestError ? (
                  <li className="rounded-md border border-[var(--pp-status-failed-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-primary)]">
                    <span className="mr-2 font-semibold text-[var(--pp-status-failed-text)]">Error</span>
                    {eventMessage(latestError)}
                  </li>
                ) : null}
                {latestDone ? (
                  <li className="rounded-md border border-[var(--pp-status-completed-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-primary)]">
                    <span className="mr-2 font-semibold text-[var(--pp-status-completed-text)]">Done</span>
                    {eventMessage(latestDone)}
                  </li>
                ) : null}
                {latestStatus ? (
                  <li className="rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-surface-raised)] px-2.5 py-1.5 text-xs text-[var(--pp-text-primary)]">
                    <span className="mr-2 font-semibold text-[var(--pp-accent-text)]">Status</span>
                    {eventMessage(latestStatus)}
                  </li>
                ) : null}
              </>
            )}
          </ul>
        </div>
      ) : null}

      <ul className="mt-1 flex-1 min-h-0 space-y-2 overflow-auto overscroll-contain pr-1 text-sm">
        {events.length > 0 ? (
          renderedEvents.length > 0 ? (
            renderedEvents.map((event, index) => {
              const meta = eventMeta(event);
              return (
                <li key={`${event.ts ?? "evt"}-${index}`} className={`rounded-md border bg-[var(--pp-surface-raised)] p-2.5 ${meta.cardClass}`}>
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <p className="text-xs text-[var(--pp-text-dim)]">{event.ts ? new Date(event.ts).toLocaleTimeString() : "-"}</p>
                    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${meta.badgeClass}`}>
                      {meta.badge}
                    </span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5">{meta.icon}</span>
                    <div>
                      <p className="text-sm text-[var(--pp-text-primary)]">{eventMessage(event)}</p>
                      {event.stage ? <p className="text-xs text-[var(--pp-text-dim)]">stage: {event.stage}</p> : null}
                    </div>
                  </div>
                </li>
              );
            })
          ) : (
            <li className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-dim)]">
              No events in this filter yet.
            </li>
          )
        ) : (
          <li className="rounded-md border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] p-3 text-sm text-[var(--pp-text-dim)]">
            Timeline events will appear after a run starts.
          </li>
        )}
      </ul>
      {compact && filteredEvents.length > renderedEvents.length ? (
        <p className="mt-2 text-[11px] text-[var(--pp-text-dim)]">
          Compact view shows latest {renderedEvents.length} events.
        </p>
      ) : null}
    </section>
  );
}
