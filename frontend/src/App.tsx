import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

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

export default function App() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[var(--pp-canvas)] text-sm text-[var(--pp-text-secondary)]">
          Loading...
        </div>
      }
    >
      <Routes>
        <Route path="/" element={<TriageDashboard />} />
        <Route path="/papers" element={<PaperNotesListPage />} />
        <Route path="/papers/:slug" element={<PaperNoteDetailPage />} />
        <Route path="/workbench/:paperId" element={<AnalysisWorkbench />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
