import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { DistrictRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FormDialog } from "../components/FormDialog";
import { ResourceTable } from "../components/ResourceTable";
import { useResourceDelete } from "../hooks/useResourceDelete";
import { useResourceList } from "../hooks/useResourceList";
import { DistrictForm, type DistrictBody } from "./DistrictForm";

export function DistrictsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  // null = closed; { row: null } = create; { row } = edit
  const [dialog, setDialog] = useState<{ row: DistrictRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const list = useResourceList<DistrictRead>({
    queryKey: ["districts"],
    fetchRows: async () => {
      const { data, error } = await client.GET("/districts/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    search,
    searchText: (d) => `${d.name} ${d.abbreviation}`,
  });

  const saveMutation = useMutation({
    mutationFn: async (body: DistrictBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/districts/{district_id}", {
          params: { path: { district_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/districts/", {
        body: body as { name: string; abbreviation: string },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      clearDeleteError();
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["districts"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const {
    confirmDelete,
    error: deleteError,
    clearError: clearDeleteError,
  } = useResourceDelete<DistrictRead>({
    queryKey: ["districts"],
    describe: (d) => `Delete district "${d.name}"?`,
    remove: async (d) => {
      const { error } = await client.DELETE("/districts/{district_id}", {
        params: { path: { district_id: d.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Districts</h1>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New district
        </button>
      </div>
      <label className="mb-3 block text-sm">
        Search
        <input
          aria-label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-2 rounded border border-gray-300 p-1"
        />
      </label>
      <ErrorBanner message={list.error ?? deleteError} />
      {list.loaded && (
        <ResourceTable
          rows={list.rows}
          columns={[
            { header: "Name", render: (d) => d.name },
            { header: "Abbreviation", render: (d) => d.abbreviation },
          ]}
          rowLabel={(d) => d.name}
          onEdit={(d) => {
            setFormError(null);
            setDialog({ row: d });
          }}
          onDelete={confirmDelete}
          emptyMessage="No districts yet."
        />
      )}
      <FormDialog
        open={dialog !== null}
        title={dialog?.row ? "Edit district" : "New district"}
      >
        {dialog && (
          <DistrictForm
            key={dialog.row?.id ?? "new"}
            initial={dialog.row}
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
