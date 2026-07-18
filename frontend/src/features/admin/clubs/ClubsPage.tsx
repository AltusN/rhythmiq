import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { ClubRead, DistrictRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FormDialog } from "../components/FormDialog";
import { ResourceTable } from "../components/ResourceTable";
import { useResourceDelete } from "../hooks/useResourceDelete";
import { useResourceList } from "../hooks/useResourceList";
import { ClubForm, type ClubBody } from "./ClubForm";

export function ClubsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [districtFilter, setDistrictFilter] = useState("");
  // null = closed; { row: null } = create; { row } = edit
  const [dialog, setDialog] = useState<{ row: ClubRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const districtsQuery = useQuery({
    queryKey: ["districts"],
    queryFn: async (): Promise<DistrictRead[]> => {
      const { data, error } = await client.GET("/districts/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const districtId = districtFilter === "" ? undefined : Number(districtFilter);
  const list = useResourceList<ClubRead>({
    queryKey: ["clubs", { district_id: districtId }],
    fetchRows: async () => {
      const { data, error } = await client.GET("/clubs/", {
        params: { query: districtId === undefined ? {} : { district_id: districtId } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    search,
    searchText: (c) => `${c.name} ${c.abbreviation}`,
  });

  const saveMutation = useMutation({
    mutationFn: async (body: ClubBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/clubs/{club_id}", {
          params: { path: { club_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/clubs/", {
        body: body as { name: string; abbreviation: string; district_id: number },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      clearDeleteError();
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["clubs"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  // Club deletes are rejected outright (409, RESTRICT) when the club still has
  // gymnasts, coaches or groups — unlike Gymnast, nothing cascades. The confirm
  // copy makes no promise about dependents; the backend's 409 detail explains
  // why a delete didn't happen when it doesn't.
  const {
    confirmDelete,
    error: deleteError,
    clearError: clearDeleteError,
  } = useResourceDelete<ClubRead>({
    queryKey: ["clubs"],
    describe: (c) => `Delete club "${c.name}"?`,
    remove: async (c) => {
      const { error } = await client.DELETE("/clubs/{club_id}", {
        params: { path: { club_id: c.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });

  const districtName = (id: number) =>
    districtsQuery.data?.find((d) => d.id === id)?.name ?? "—";

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Clubs</h1>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New club
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
          District filter
          <select
            aria-label="District filter"
            value={districtFilter}
            onChange={(e) => setDistrictFilter(e.target.value)}
            className="ml-2 rounded border border-gray-300 p-1"
          >
            <option value="">All districts</option>
            {districtsQuery.data?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ErrorBanner
        message={
          list.error ||
          (districtsQuery.error ? districtsQuery.error.message : null) ||
          deleteError
        }
      />
      {list.loaded && (
        <ResourceTable
          rows={list.rows}
          columns={[
            { header: "Name", render: (c) => c.name },
            { header: "Abbreviation", render: (c) => c.abbreviation },
            { header: "District", render: (c) => districtName(c.district_id) },
          ]}
          rowLabel={(c) => c.name}
          onEdit={(c) => {
            setFormError(null);
            setDialog({ row: c });
          }}
          onDelete={confirmDelete}
          emptyMessage="No clubs yet."
        />
      )}
      <FormDialog open={dialog !== null} title={dialog?.row ? "Edit club" : "New club"}>
        {dialog && (
          <ClubForm
            key={dialog.row?.id ?? "new"}
            initial={dialog.row}
            districts={districtsQuery.data ?? []}
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
