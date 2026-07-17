import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { EntriesPage } from "./features/entries/EntriesPage";
import { MeetListPage } from "./features/meets/MeetListPage";
import { MeetShell } from "./features/meets/MeetShell";
import { ScoringPage } from "./features/scoring/ScoringPage";
import { StandingsPage } from "./features/standings/StandingsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<MeetListPage />} />
        <Route path="/meets/:meetId" element={<MeetShell />}>
          <Route index element={<Navigate to="scoring" replace />} />
          <Route path="scoring" element={<ScoringPage />} />
          <Route path="entries" element={<EntriesPage />} />
          <Route path="standings" element={<StandingsPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
