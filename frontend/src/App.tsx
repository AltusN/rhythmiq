import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AdminShell } from "./features/admin/AdminShell";
import { ClubsPage } from "./features/admin/clubs/ClubsPage";
import { CoachesPage } from "./features/admin/coaches/CoachesPage";
import { DistrictsPage } from "./features/admin/districts/DistrictsPage";
import { GroupsPage } from "./features/admin/groups/GroupsPage";
import { GymnastsPage } from "./features/admin/gymnasts/GymnastsPage";
import { JudgesPage } from "./features/admin/judges/JudgesPage";
import { RoutineProfilesPage } from "./features/admin/routine-profiles/RoutineProfilesPage";
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
        <Route path="/admin" element={<AdminShell />}>
          <Route index element={<Navigate to="districts" replace />} />
          <Route path="districts" element={<DistrictsPage />} />
          <Route path="clubs" element={<ClubsPage />} />
          <Route path="coaches" element={<CoachesPage />} />
          <Route path="groups" element={<GroupsPage />} />
          <Route path="gymnasts" element={<GymnastsPage />} />
          <Route path="judges" element={<JudgesPage />} />
          <Route path="routine-profiles" element={<RoutineProfilesPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
