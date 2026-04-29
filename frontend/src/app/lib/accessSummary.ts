import { PaperAccessSummary } from "./types";

export interface PaperAccessSummaryDisplay {
  label: string;
  tone: "success" | "warning" | "accent" | "muted";
  href?: string | null;
  linkLabel?: string;
}

export function getPaperAccessSummaryDisplay(summary?: PaperAccessSummary | null): PaperAccessSummaryDisplay {
  if (!summary) {
    return { label: "No route", tone: "muted" };
  }
  if (summary.status_label === "open") {
    return {
      label: "Open access",
      tone: "success",
      href: summary.open_access_url,
      linkLabel: "Open available PDF",
    };
  }
  if (summary.status_label === "institution_required") {
    return {
      label: "Institution route",
      tone: "warning",
      href: summary.institution_access_url,
      linkLabel: "Open institution page",
    };
  }
  if (summary.status_label === "user_imported_pdf") {
    return {
      label: "Local PDF",
      tone: "accent",
      href: summary.local_pdf_url,
      linkLabel: "Open saved PDF",
    };
  }
  return { label: "No route", tone: "muted" };
}
