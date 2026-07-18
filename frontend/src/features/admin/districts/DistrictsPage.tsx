import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { DistrictRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { DistrictForm, type DistrictBody } from "./DistrictForm";

export function DistrictsPage() {
  const queryClient = useQueryClient();
  // null = closed; { row: null } = create; { row } = edit
  const [dialog, setDialog] = useState<{ row: DistrictRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  const districtsQuery = useQuery({
    queryKey: ["districts"],
    queryFn: async (): Promise<DistrictRead[]> => {
      const { data, error } = await client.GET("/districts/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
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
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["districts"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: async (row: DistrictRead) => {
      const { error } = await client.DELETE("/districts/{district_id}", {
        params: { path: { district_id: row.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
    onSuccess: () => {
      setListError(null);
      queryClient.invalidateQueries({ queryKey: ["districts"] });
    },
    onError: (e: Error) => setListError(e.message),
  });

  const confirmDelete = (row: DistrictRead) => {
    if (!window.confirm(`Delete district "${row.name}"?`)) return;
    deleteMutation.mutate(row);
  };

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
      <ErrorBanner
        message={districtsQuery.error ? districtsQuery.error.message : listError}
      />
      {districtsQuery.data?.length === 0 && (
        <p className="text-sm text-gray-500">No districts yet.</p>
      )}
      {districtsQuery.data && districtsQuery.data.length > 0 && (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-300 text-left">
              <th className="py-1">Name</th>
              <th className="py-1">Abbreviation</th>
              <th className="py-1" />
            </tr>
          </thead>
          <tbody>
            {districtsQuery.data.map((d) => (
              <tr key={d.id} className="border-b border-gray-200">
                <td className="py-1">{d.name}</td>
                <td className="py-1">{d.abbreviation}</td>
                <td className="py-1 text-right">
                  <button
                    type="button"
                    aria-label={`Edit ${d.name}`}
                    onClick={() => {
                      setFormError(null);
                      setDialog({ row: d });
                    }}
                    className="rounded border border-gray-300 px-2 py-0.5 text-xs"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${d.name}`}
                    onClick={() => confirmDelete(d)}
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
              {dialog.row ? "Edit district" : "New district"}
            </h2>
            <DistrictForm
              key={dialog.row?.id ?? "new"}
              initial={dialog.row}
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
