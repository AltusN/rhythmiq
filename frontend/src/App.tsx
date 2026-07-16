import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { MeetListPage } from "./features/meets/MeetListPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<MeetListPage />} />
      </Route>
    </Routes>
  );
}
