import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { ClubRead, GymnastRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";

export function GymnastsPage() {
  const [search, setSearch] = useState("");
  const [clubFilter, setClubFilter] = useState("");

  const clubsQuery = useQuery({
    queryKey: ["clubs", {}],
    queryFn: async (): Promise<ClubRead[]> => {
      const { data, error } = await client.GET("/clubs/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const clubId = clubFilter === "" ? undefined : Number(clubFilter);
  const gymnastsQuery = useQuery({
    queryKey: ["gymnasts", { club_id: clubId }],
    queryFn: async (): Promise<GymnastRead[]> => {
      const { data, error } = await client.GET("/gymnasts/", {
        params: { query: clubId === undefined ? {} : { club_id: clubId } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const clubName = (id: number | null | undefined) =>
    id === null ? "—" : (clubsQuery.data?.find((c) => c.id === id)?.name ?? "—");

  const needle = search.trim().toLowerCase();
  const rows = (gymnastsQuery.data ?? []).filter((g) =>
    needle === ""
      ? true
      : `${g.first_name} ${g.last_name}`.toLowerCase().includes(needle),
  );

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Gymnasts</h1>
      </div>
      <div className="mb-3 flex gap-3">
        <label className="text-sm">
          Search
          <input
            aria-label="Search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="ml-2 rounded border border-gray-300 p-1"
          />
        </label>
        <label className="text-sm">
          Club filter
          <select
            aria-label="Club filter"
            value={clubFilter}
            onChange={(e) => setClubFilter(e.target.value)}
            className="ml-2 rounded border border-gray-300 p-1"
          >
            <option value="">All clubs</option>
            {clubsQuery.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ErrorBanner message={gymnastsQuery.error ? gymnastsQuery.error.message : null} />
      {gymnastsQuery.data && rows.length === 0 && (
        <p className="text-sm text-gray-500">No gymnasts yet.</p>
      )}
      {rows.length > 0 && (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-300 text-left">
              <th className="py-1">Name</th>
              <th className="py-1">Club</th>
              <th className="py-1">Date of birth</th>
              <th className="py-1">Country</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((g) => (
              <tr key={g.id} className="border-b border-gray-200">
                <td className="py-1">
                  {g.first_name} {g.last_name}
                </td>
                <td className="py-1">{clubName(g.club_id)}</td>
                <td className="py-1">{g.date_of_birth ?? "—"}</td>
                <td className="py-1">{g.country_code ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
