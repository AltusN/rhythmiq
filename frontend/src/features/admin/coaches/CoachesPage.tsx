import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { ClubRead, CoachRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FormDialog } from "../components/FormDialog";
import { ResourceTable } from "../components/ResourceTable";
import { useResourceDelete } from "../hooks/useResourceDelete";
import { useResourceList } from "../hooks/useResourceList";
import { CoachForm, type CoachBody } from "./CoachForm";

export function CoachesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [clubFilter, setClubFilter] = useState("");
  // null = closed; { row: null } = create; { row } = edit
  const [dialog, setDialog] = useState<{ row: CoachRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const clubsQuery = useQuery({
    queryKey: ["clubs", {}],
    queryFn: async (): Promise<ClubRead[]> => {
      const { data, error } = await client.GET("/clubs/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const clubId = clubFilter === "" ? undefined : Number(clubFilter);
  const list = useResourceList<CoachRead>({
    queryKey: ["coaches", { club_id: clubId }],
    fetchRows: async () => {
      const { data, error } = await client.GET("/coaches/", {
        params: { query: clubId === undefined ? {} : { club_id: clubId } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    search,
    searchText: (c) => `${c.first_name} ${c.last_name}`,
  });

  const saveMutation = useMutation({
    mutationFn: async (body: CoachBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/coaches/{coach_id}", {
          params: { path: { coach_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/coaches/", {
        body: body as {
          first_name: string;
          last_name: string;
          club_id: number;
          is_head_coach: boolean;
        },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      clearDeleteError();
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["coaches"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  // Nothing in the schema FKs to coaches.id, so a coach delete has no known
  // dependents today — unlike Club/District/Group (RESTRICT) or Gymnast
  // (cascade). The router still guards commit() with a defensive 409, so the
  // confirm copy makes no promise either way and any 409 detail surfaces via
  // ErrorBanner the same as every other resource.
  const {
    confirmDelete,
    error: deleteError,
    clearError: clearDeleteError,
  } = useResourceDelete<CoachRead>({
    queryKey: ["coaches"],
    describe: (c) => `Delete coach "${c.first_name} ${c.last_name}"?`,
    remove: async (c) => {
      const { error } = await client.DELETE("/coaches/{coach_id}", {
        params: { path: { coach_id: c.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });

  const clubName = (id: number) => clubsQuery.data?.find((c) => c.id === id)?.name ?? "—";

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Coaches</h1>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New coach
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
            onChange={(e) => {
              setClubFilter(e.target.value);
              clearDeleteError();
            }}
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
          list.error || (clubsQuery.error ? clubsQuery.error.message : null) || deleteError
        }
      />
      {list.loaded && (
        <ResourceTable
          rows={list.rows}
          columns={[
            { header: "Name", render: (c) => `${c.first_name} ${c.last_name}` },
            { header: "Club", render: (c) => clubName(c.club_id) },
            { header: "Role", render: (c) => (c.is_head_coach ? "Head coach" : "Assistant") },
          ]}
          rowLabel={(c) => `${c.first_name} ${c.last_name}`}
          onEdit={(c) => {
            setFormError(null);
            setDialog({ row: c });
          }}
          onDelete={confirmDelete}
          emptyMessage="No coaches yet."
        />
      )}
      <FormDialog
        open={dialog !== null}
        title={dialog?.row ? "Edit coach" : "New coach"}
        onClose={() => setDialog(null)}
      >
        {dialog && (
          <CoachForm
            key={dialog.row?.id ?? "new"}
            initial={dialog.row}
            clubs={clubsQuery.data ?? []}
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
