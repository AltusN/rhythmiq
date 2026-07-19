import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { JudgeRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FormDialog } from "../components/FormDialog";
import { ResourceTable } from "../components/ResourceTable";
import { useResourceDelete } from "../hooks/useResourceDelete";
import { useResourceList } from "../hooks/useResourceList";
import { JudgeForm, type JudgeBody } from "./JudgeForm";

/** Countries offered by the filter. Judges are few; a free-text filter would be worse. */
const COUNTRIES = ["RSA", "BUL", "RUS", "ESP", "ITA", "JPN", "UKR", "USA"];

export function JudgesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [country, setCountry] = useState("");
  const [dialog, setDialog] = useState<{ row: JudgeRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const list = useResourceList<JudgeRead>({
    queryKey: ["judges", country],
    fetchRows: async () => {
      const { data, error } = await client.GET("/judges/", {
        params: { query: country === "" ? {} : { country_code: country } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    search,
    searchText: (j) => `${j.first_name} ${j.last_name} ${j.brevet ?? ""}`,
  });

  const saveMutation = useMutation({
    mutationFn: async (body: JudgeBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/judges/{judge_id}", {
          params: { path: { judge_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/judges/", {
        body: body as { first_name: string; last_name: string },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      clearDeleteError();
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["judges"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const {
    confirmDelete,
    error: deleteError,
    clearError: clearDeleteError,
  } = useResourceDelete<JudgeRead>({
    queryKey: ["judges"],
    // JudgeScore.judge_id and PenaltyRecord.judge_id are both ondelete="RESTRICT",
    // so a judge with scores or penalties can't be deleted at all — nothing cascades.
    // The 409 detail says so; the confirm copy must not promise otherwise.
    describe: (j) => `Delete judge "${j.first_name} ${j.last_name}"?`,
    remove: async (j) => {
      const { error } = await client.DELETE("/judges/{judge_id}", {
        params: { path: { judge_id: j.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Judges</h1>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New judge
        </button>
      </div>
      <div className="mb-3 flex gap-4">
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
          Country
          <select
            aria-label="Country"
            value={country}
            onChange={(e) => {
              clearDeleteError();
              setCountry(e.target.value);
            }}
            className="ml-2 rounded border border-gray-300 p-1"
          >
            <option value="">— all —</option>
            {COUNTRIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ErrorBanner message={list.error ?? deleteError} />
      {list.loaded && (
        <ResourceTable
          rows={list.rows}
          columns={[
            { header: "First name", render: (j) => j.first_name },
            { header: "Last name", render: (j) => j.last_name },
            { header: "Country", render: (j) => j.country_code ?? "—" },
            { header: "Brevet", render: (j) => j.brevet ?? "—" },
          ]}
          rowLabel={(j) => `${j.first_name} ${j.last_name}`}
          onEdit={(j) => {
            setFormError(null);
            setDialog({ row: j });
          }}
          onDelete={confirmDelete}
          emptyMessage="No judges yet."
        />
      )}
      <FormDialog
        open={dialog !== null}
        title={dialog?.row ? "Edit judge" : "New judge"}
        onClose={() => setDialog(null)}
      >
        {dialog && (
          <JudgeForm
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
