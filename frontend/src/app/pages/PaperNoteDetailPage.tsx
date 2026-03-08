import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link, useParams } from "react-router-dom";
import { ExternalLink, FlaskConical } from "lucide-react";
import { getApiErrorMessage, getPaperNoteDetail } from "../lib/api";
import { PaperNoteDetailResponse } from "../lib/types";

function formatDate(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString();
}

function confidenceLabel(value?: number | null): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(2);
}

function resolveWorkbenchPaperId(note: PaperNoteDetailResponse["note"] | null): string | null {
  if (!note) {
    return null;
  }
  const id = (note.id ?? "").trim();
  if (id.length > 0) {
    return id;
  }
  if (note.slug.startsWith("zotero") && !note.slug.includes(":")) {
    return `zotero:${note.slug.slice("zotero".length)}`;
  }
  return note.slug;
}

export function PaperNoteDetailPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug ?? "";

  const [data, setData] = useState<PaperNoteDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      if (!slug) {
        setLoadError("Missing note slug.");
        setLoading(false);
        return;
      }
      setLoading(true);
      setLoadError(null);
      try {
        const result = await getPaperNoteDetail(slug);
        if (!mounted) {
          return;
        }
        setData(result.data);
      } catch (error) {
        if (!mounted) {
          return;
        }
        setData(null);
        setLoadError(getApiErrorMessage(error));
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      mounted = false;
    };
  }, [slug]);

  const note = data?.note ?? null;
  const aliases = useMemo(() => note?.aliases ?? [], [note]);
  const tags = useMemo(() => note?.tags ?? [], [note]);
  const workbenchPaperId = useMemo(() => resolveWorkbenchPaperId(note), [note]);

  useEffect(() => {
    if (note?.title) {
      document.title = `${note.title} | Lattice`;
      return;
    }
    if (slug) {
      document.title = `${slug} | Lattice`;
      return;
    }
    document.title = "Paper Note | Lattice";
  }, [note?.title, slug]);

  return (
    <div className="min-h-screen bg-[var(--pp-canvas)] p-4 pb-24 md:pb-4">
      <header className="surface-card mb-4 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pp-text-dim)]">Lattice · Paper Notes Viewer</p>
            <h1 className="mt-1 text-xl font-semibold text-[var(--pp-text-primary)]">{note?.title ?? slug}</h1>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <Link to="/papers" className="text-[var(--pp-accent-text)] underline-offset-2 hover:underline">
              ← Back to list
            </Link>
            {workbenchPaperId ? (
              <Link
                to={`/workbench/${encodeURIComponent(workbenchPaperId)}`}
                className="hidden items-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2.5 py-1.5 text-xs font-medium text-[var(--pp-accent-text)] md:inline-flex"
              >
                <FlaskConical className="h-3.5 w-3.5" />
                Open in Workbench
              </Link>
            ) : (
              <Link to="/" className="text-[var(--pp-text-secondary)] underline-offset-2 hover:underline">
                Workbench
              </Link>
            )}
          </div>
        </div>
        {note?.id ? <p className="mt-2 text-xs text-[var(--pp-text-dim)]">{note.id}</p> : null}
      </header>

      {loading ? <p className="text-sm text-[var(--pp-text-dim)]">Loading note...</p> : null}
      {loadError ? <p className="text-sm text-[var(--pp-status-failed-text)]">API error: {loadError}</p> : null}

      {!loading && !loadError && data ? (
        <main className="grid grid-cols-1 gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <aside className="surface-card p-4">
            <h2 className="text-base font-semibold text-[var(--pp-text-primary)]">Properties</h2>

            <dl className="mt-3 space-y-3 text-sm">
              <div>
                <dt className="text-xs text-[var(--pp-text-dim)]">id</dt>
                <dd className="mt-1 break-all text-[var(--pp-text-primary)]">{note?.id ?? "-"}</dd>
              </div>
              <div>
                <dt className="text-xs text-[var(--pp-text-dim)]">aliases</dt>
                <dd className="mt-1 text-[var(--pp-text-primary)]">{aliases.length > 0 ? aliases.join(" | ") : "-"}</dd>
              </div>
              <div>
                <dt className="text-xs text-[var(--pp-text-dim)]">tags</dt>
                <dd className="mt-1 flex flex-wrap gap-1.5">
                  {tags.length === 0 ? <span className="text-[var(--pp-text-primary)]">-</span> : null}
                  {tags.map((tag) => (
                    <span
                      key={`tag-${tag}`}
                      className="inline-flex rounded-full border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-2 py-0.5 text-xs text-[var(--pp-accent-text)]"
                    >
                      {tag}
                    </span>
                  ))}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-[var(--pp-text-dim)]">date_processed</dt>
                <dd className="mt-1 text-[var(--pp-text-primary)]">{formatDate(note?.date_processed)}</dd>
              </div>
              <div>
                <dt className="text-xs text-[var(--pp-text-dim)]">confidence</dt>
                <dd className="mt-1 text-[var(--pp-text-primary)]">{confidenceLabel(note?.confidence)}</dd>
              </div>
              <div>
                <dt className="text-xs text-[var(--pp-text-dim)]">status</dt>
                <dd className="mt-1 text-[var(--pp-text-primary)]">{note?.status ?? "-"}</dd>
              </div>
            </dl>
          </aside>

          <section className="surface-card p-4">
            <article className="paper-note-markdown">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a({ href, children }) {
                    if (!href) {
                      return <span>{children}</span>;
                    }
                    if (href.startsWith("/papers/")) {
                      return (
                        <Link to={href} className="paper-note-link">
                          {children}
                        </Link>
                      );
                    }
                    return (
                      <a href={href} target="_blank" rel="noreferrer" className="paper-note-link">
                        {children}
                      </a>
                    );
                  },
                }}
              >
                {data.body_markdown}
              </ReactMarkdown>
            </article>

            <section className="mt-8">
              <h2 className="text-2xl font-semibold text-[var(--pp-text-primary)]">Related Papers</h2>
              {data.related.length === 0 ? (
                <p className="mt-2 text-sm text-[var(--pp-text-dim)]">No related papers found by shared tags.</p>
              ) : (
                <ul className="mt-2 list-disc space-y-2 pl-5">
                  {data.related.map((item) => (
                    <li key={`related-${item.slug}`} className="text-base text-[var(--pp-text-primary)]">
                      <Link to={`/papers/${encodeURIComponent(item.slug)}`} className="paper-note-link">
                        {item.title}
                      </Link>{" "}
                      <span className="text-[var(--pp-text-secondary)]">(shared tags: {item.shared_tags.join(", ")})</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="mt-8">
              <h2 className="text-2xl font-semibold text-[var(--pp-text-primary)]">References</h2>
              {data.references.length === 0 ? (
                <p className="mt-2 text-sm text-[var(--pp-text-dim)]">No references available.</p>
              ) : (
                <ul className="mt-2 list-disc space-y-2 pl-5">
                  {data.references.map((reference, idx) => (
                    <li key={`reference-${idx}`} className="text-base text-[var(--pp-text-primary)]">
                      <a href={reference.url} target="_blank" rel="noreferrer" className="paper-note-link inline-flex items-center gap-1">
                        {reference.label}
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>{" "}
                      <span className="text-xs uppercase text-[var(--pp-text-dim)]">{reference.source}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {workbenchPaperId ? (
              <section className="mt-8 hidden md:block">
                <Link
                  to={`/workbench/${encodeURIComponent(workbenchPaperId)}`}
                  className="inline-flex items-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-3 py-2 text-sm font-medium text-[var(--pp-accent-text)]"
                >
                  <FlaskConical className="h-4 w-4" />
                  Open in Workbench
                </Link>
              </section>
            ) : null}
          </section>
        </main>
      ) : null}

      {workbenchPaperId ? (
        <div className="fixed bottom-3 left-3 right-3 z-30 md:hidden">
          <Link
            to={`/workbench/${encodeURIComponent(workbenchPaperId)}`}
            className="inline-flex w-full items-center justify-center gap-1 rounded-md border border-[var(--pp-accent-border)] bg-[var(--pp-accent-soft)] px-3 py-2 text-sm font-medium text-[var(--pp-accent-text)] shadow-[var(--pp-shadow)]"
          >
            <FlaskConical className="h-4 w-4" />
            Open in Workbench
          </Link>
        </div>
      ) : null}
    </div>
  );
}
