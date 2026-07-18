import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { ClubRead, GroupRead, GymnastRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { GymnastForm, type GymnastBody } from "./GymnastForm";

export function GymnastsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [clubFilter, setClubFilter] = useState("");
  // null = closed; { row: null } = create; { row } = edit
  const [dialog, setDialog] = useState<{ row: GymnastRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  const clubsQuery = useQuery({
    queryKey: ["clubs", {}],
    queryFn: async (): Promise<ClubRead[]> => {
      const { data, error } = await client.GET("/clubs/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const groupsQuery = useQuery({
    queryKey: ["groups", {}],
    queryFn: async (): Promise<GroupRead[]> => {
      const { data, error } = await client.GET("/groups/");
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

  const saveMutation = useMutation({
    mutationFn: async (body: GymnastBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/gymnasts/{gymnast_id}", {
          params: { path: { gymnast_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/gymnasts/", {
        body: body as { first_name: string; last_name: string },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      setListError(null);
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["gymnasts"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: async (row: GymnastRead) => {
      const { error } = await client.DELETE("/gymnasts/{gymnast_id}", {
        params: { path: { gymnast_id: row.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
    onSuccess: () => {
      setListError(null);
      queryClient.invalidateQueries({ queryKey: ["gymnasts"] });
    },
    onError: (e: Error) => setListError(e.message),
  });

  const confirmDelete = (row: GymnastRead) => {
    const name = `${row.first_name} ${row.last_name}`;
    if (
      !window.confirm(
        `Delete gymnast "${name}"? This also deletes their meet entries and routines.`,
      )
    )
      return;
    deleteMutation.mutate(row);
  };

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
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New gymnast
        </button>
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
      <ErrorBanner
        message={
          (gymnastsQuery.error ? gymnastsQuery.error.message : null) ||
          (clubsQuery.error ? clubsQuery.error.message : null) ||
          (groupsQuery.error ? groupsQuery.error.message : null) ||
          listError
        }
      />
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
              <th className="py-1" />
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
                <td className="py-1 text-right">
                  <button
                    type="button"
                    aria-label={`Edit ${g.first_name} ${g.last_name}`}
                    onClick={() => {
                      setFormError(null);
                      setDialog({ row: g });
                    }}
                    className="rounded border border-gray-300 px-2 py-0.5 text-xs"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${g.first_name} ${g.last_name}`}
                    onClick={() => confirmDelete(g)}
                    className="ml-2 rounded border border-gray-300 px-2 py-0.5 text-xs text-red-700"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {dialog && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/30">
          <div className="w-96 rounded border border-gray-200 bg-white p-4 shadow-lg">
            <h2 className="mb-2 text-lg font-semibold">
              {dialog.row ? "Edit gymnast" : "New gymnast"}
            </h2>
            <GymnastForm
              key={dialog.row?.id ?? "new"}
              initial={dialog.row}
              clubs={clubsQuery.data ?? []}
              groups={groupsQuery.data ?? []}
              pending={saveMutation.isPending}
              error={formError}
              onSubmit={(body) => saveMutation.mutate(body)}
              onCancel={() => setDialog(null)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
