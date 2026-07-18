import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { ClubRead, GroupRead, GymnastRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FormDialog } from "../components/FormDialog";
import { ResourceTable } from "../components/ResourceTable";
import { useResourceDelete } from "../hooks/useResourceDelete";
import { useResourceList } from "../hooks/useResourceList";
import { GymnastForm, type GymnastBody } from "./GymnastForm";

export function GymnastsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [clubFilter, setClubFilter] = useState("");
  // null = closed; { row: null } = create; { row } = edit
  const [dialog, setDialog] = useState<{ row: GymnastRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

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
  const list = useResourceList<GymnastRead>({
    queryKey: ["gymnasts", { club_id: clubId }],
    fetchRows: async () => {
      const { data, error } = await client.GET("/gymnasts/", {
        params: { query: clubId === undefined ? {} : { club_id: clubId } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    search,
    searchText: (g) => `${g.first_name} ${g.last_name}`,
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
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["gymnasts"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const { confirmDelete, error: deleteError } = useResourceDelete<GymnastRead>({
    queryKey: ["gymnasts", { club_id: clubId }],
    describe: (g) =>
      `Delete gymnast "${g.first_name} ${g.last_name}"? This also deletes their meet entries and routines.`,
    remove: async (g) => {
      const { error } = await client.DELETE("/gymnasts/{gymnast_id}", {
        params: { path: { gymnast_id: g.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });

  const clubName = (id: number | null | undefined) =>
    id === null ? "—" : (clubsQuery.data?.find((c) => c.id === id)?.name ?? "—");

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
          list.error ||
          (clubsQuery.error ? clubsQuery.error.message : null) ||
          (groupsQuery.error ? groupsQuery.error.message : null) ||
          deleteError
        }
      />
      {list.loaded && (
        <ResourceTable
          rows={list.rows}
          columns={[
            { header: "Name", render: (g) => `${g.first_name} ${g.last_name}` },
            { header: "Club", render: (g) => clubName(g.club_id) },
            { header: "Date of birth", render: (g) => g.date_of_birth ?? "—" },
            { header: "Country", render: (g) => g.country_code ?? "—" },
          ]}
          rowLabel={(g) => `${g.first_name} ${g.last_name}`}
          onEdit={(g) => {
            setFormError(null);
            setDialog({ row: g });
          }}
          onDelete={confirmDelete}
          emptyMessage="No gymnasts yet."
        />
      )}
      <FormDialog
        open={dialog !== null}
        title={dialog?.row ? "Edit gymnast" : "New gymnast"}
      >
        {dialog && (
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
        )}
      </FormDialog>
    </div>
  );
}
