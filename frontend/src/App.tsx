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

export default function App() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[var(--pp-canvas)] text-sm text-[var(--pp-text-secondary)]">
          Loading workspace...
        </div>
      }
    >
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
        <Route path="/workbench/:paperId" element={<AnalysisWorkbench />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
