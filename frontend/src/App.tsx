import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { MeetListPage } from "./features/meets/MeetListPage";
import { MeetShell } from "./features/meets/MeetShell";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<MeetListPage />} />
        <Route path="/meets/:meetId" element={<MeetShell />}>
          <Route index element={<Navigate to="scoring" replace />} />
          <Route path="scoring" element={<div>Scoring coming soon</div>} />
          <Route path="entries" element={<div>Entries coming soon</div>} />
          <Route path="standings" element={<div>Standings coming soon</div>} />
        </Route>
      </Route>
    </Routes>
  );
}
