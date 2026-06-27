import { Navigate, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Jobs from "./pages/Jobs";
import SectionAnalysis from "./pages/SectionAnalysis";
import SectionDetail from "./pages/SectionDetail";
import SemanticAnalysis from "./pages/SemanticAnalysis";
import Statements from "./pages/Statements";
import UploadPage from "./pages/Upload";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/jobs" replace />} />
      <Route path="/upload" element={<UploadPage />} />

      <Route path="/section-analysis" element={<SectionAnalysis />} />
      <Route
        path="/section-analysis/:jobId"
        element={<SectionAnalysis />}
      />
      <Route
        path="/section-analysis/:jobId/:sectionName"
        element={<SectionAnalysis />}
      />

      <Route path="/semantic-analysis" element={<SemanticAnalysis />} />
      <Route
        path="/semantic-analysis/:jobId"
        element={<SemanticAnalysis />}
      />
      <Route
        path="/semantic-analysis/:jobId/:sectionName"
        element={<SemanticAnalysis />}
      />

      <Route path="/jobs" element={<Jobs />} />
      <Route path="/jobs/:jobId" element={<Dashboard />} />
      <Route
        path="/jobs/:jobId/sections/:sectionName"
        element={<SectionDetail />}
      />
      <Route path="/jobs/:jobId/statements" element={<Statements />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
