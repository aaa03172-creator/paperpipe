import { lazy, Suspense, useEffect } from "react";
import { House } from "lucide-react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";

const TriageDashboard = lazy(async () => {
  const module = await import("./app/pages/TriageDashboard");
  return { default: module.TriageDashboard };
});

const AnalysisWorkbench = lazy(async () => {
  const module = await import("./app/pages/AnalysisWorkbench");
  return { default: module.AnalysisWorkbench };
});

const PaperNotesListPage = lazy(async () => {
  const module = await import("./app/pages/PaperNotesListPage");
  return { default: module.PaperNotesListPage };
});

const PaperNoteDetailPage = lazy(async () => {
  const module = await import("./app/pages/PaperNoteDetailPage");
  return { default: module.PaperNoteDetailPage };
});

const MeetingPackPage = lazy(async () => {
  const module = await import("./app/pages/MeetingPackPage");
  return { default: module.MeetingPackPage };
});

const MethodComparisonPage = lazy(async () => {
  const module = await import("./app/pages/MethodComparisonPage");
  return { default: module.MethodComparisonPage };
});

const ChartPackPage = lazy(async () => {
  const module = await import("./app/pages/ChartPackPage");
  return { default: module.ChartPackPage };
});

const ImageEvidencePage = lazy(async () => {
  const module = await import("./app/pages/ImageEvidencePage");
  return { default: module.ImageEvidencePage };
});

const ProtocolCardPage = lazy(async () => {
  const module = await import("./app/pages/ProtocolCardPage");
  return { default: module.ProtocolCardPage };
});

const RuntimeReadinessPage = lazy(async () => {
  const module = await import("./app/pages/RuntimeReadinessPage");
  return { default: module.RuntimeReadinessPage };
});

const SettingsPage = lazy(async () => {
  const module = await import("./app/pages/SettingsPage");
  return { default: module.SettingsPage };
});

function GlobalHomeButton() {
  const location = useLocation();
  const hideOnPrimaryPaperLoop = location.pathname === "/" || location.pathname === "/papers";
  if (hideOnPrimaryPaperLoop) {
    return null;
  }
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 sm:bottom-5 sm:right-5">
      <Link
        to="/"
        className="pointer-events-auto inline-flex items-center gap-2 rounded-full border border-[var(--pp-border)] bg-[var(--pp-surface-raised)] px-3 py-2 text-xs font-medium text-[var(--pp-text-primary)] shadow-[var(--pp-shadow)] transition-colors hover:bg-[var(--pp-surface)]"
      >
        <House className="h-3.5 w-3.5" />
        Home
      </Link>
    </div>
  );
}

function RouteFocusReset() {
  const location = useLocation();

  useEffect(() => {
    if (location.hash) {
      return;
    }
    const previousTabIndex = document.body.getAttribute("tabindex");
    document.body.setAttribute("tabindex", "-1");
    const resetFocus = window.setTimeout(() => {
      document.body.focus({ preventScroll: true });
    }, 0);
    return () => {
      window.clearTimeout(resetFocus);
      if (previousTabIndex === null) {
        document.body.removeAttribute("tabindex");
      } else {
        document.body.setAttribute("tabindex", previousTabIndex);
      }
    };
  }, [location.hash, location.pathname]);

  return null;
}

export default function App() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[var(--pp-canvas)] text-sm text-[var(--pp-text-secondary)]">
          Loading workspace...
        </div>
      }
    >
      <RouteFocusReset />
      <GlobalHomeButton />
      <Routes>
        <Route path="/" element={<TriageDashboard />} />
        <Route path="/papers" element={<PaperNotesListPage />} />
        <Route path="/papers/:slug" element={<PaperNoteDetailPage />} />
        <Route path="/meeting-packs" element={<MeetingPackPage />} />
        <Route path="/meeting-packs/:packId" element={<MeetingPackPage />} />
        <Route path="/method-comparisons" element={<MethodComparisonPage />} />
        <Route path="/method-comparisons/:comparisonId" element={<MethodComparisonPage />} />
        <Route path="/chart-packs" element={<ChartPackPage />} />
        <Route path="/chart-packs/:chartPackId" element={<ChartPackPage />} />
        <Route path="/image-evidence" element={<ImageEvidencePage />} />
        <Route path="/image-evidence/:imageEvidenceId" element={<ImageEvidencePage />} />
        <Route path="/protocol-cards" element={<ProtocolCardPage />} />
        <Route path="/protocol-cards/:protocolId" element={<ProtocolCardPage />} />
        <Route path="/ready" element={<RuntimeReadinessPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/workbench/:paperId" element={<AnalysisWorkbench />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
