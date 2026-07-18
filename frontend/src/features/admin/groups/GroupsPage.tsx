import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { ClubRead, GroupRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FormDialog } from "../components/FormDialog";
import { ResourceTable } from "../components/ResourceTable";
import { useResourceDelete } from "../hooks/useResourceDelete";
import { useResourceList } from "../hooks/useResourceList";
import { GroupForm, type GroupBody } from "./GroupForm";

export function GroupsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [clubFilter, setClubFilter] = useState("");
  // null = closed; { row: null } = create; { row } = edit
  const [dialog, setDialog] = useState<{ row: GroupRead | null } | null>(null);
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
  const list = useResourceList<GroupRead>({
    queryKey: ["groups", { club_id: clubId }],
    fetchRows: async () => {
      const { data, error } = await client.GET("/groups/", {
        params: { query: clubId === undefined ? {} : { club_id: clubId } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    search,
    searchText: (g) => g.name,
  });

  const saveMutation = useMutation({
    mutationFn: async (body: GroupBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/groups/{group_id}", {
          params: { path: { group_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/groups/", {
        body: body as { name: string; club_id: number },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      clearDeleteError();
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  // Group deletes are rejected (409) via RESTRICT when the group still has
  // gymnast members (models.py: Gymnast.group_id FK, ondelete="RESTRICT") —
  // unlike Gymnast, whose deletes cascade. The confirm copy makes no
  // promise the backend won't keep, and any 409 detail surfaces via
  // ErrorBanner the same as every other resource.
  const {
    confirmDelete,
    error: deleteError,
    clearError: clearDeleteError,
  } = useResourceDelete<GroupRead>({
    queryKey: ["groups"],
    describe: (g) => `Delete group "${g.name}"?`,
    remove: async (g) => {
      const { error } = await client.DELETE("/groups/{group_id}", {
        params: { path: { group_id: g.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });

  const clubName = (id: number) => clubsQuery.data?.find((c) => c.id === id)?.name ?? "—";

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Groups</h1>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New group
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
            { header: "Name", render: (g) => g.name },
            { header: "Club", render: (g) => clubName(g.club_id) },
          ]}
          rowLabel={(g) => g.name}
          onEdit={(g) => {
            setFormError(null);
            setDialog({ row: g });
          }}
          onDelete={confirmDelete}
          emptyMessage="No groups yet."
        />
      )}
      <FormDialog
        open={dialog !== null}
        title={dialog?.row ? "Edit group" : "New group"}
        onClose={() => setDialog(null)}
      >
        {dialog && (
          <GroupForm
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
