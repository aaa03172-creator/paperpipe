import { Navigate, Route, Routes } from "react-router-dom";
import { TriageDashboard } from "./app/pages/TriageDashboard";
import { AnalysisWorkbench } from "./app/pages/AnalysisWorkbench";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<TriageDashboard />} />
      <Route path="/workbench/:paperId" element={<AnalysisWorkbench />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
