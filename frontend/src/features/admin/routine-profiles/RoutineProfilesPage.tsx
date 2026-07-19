import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { Apparatus, RoutineProfileRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { APPARATUS, labelize } from "../../../lib/domain";
import { useCompetitorNames } from "../../../lib/useCompetitorNames";
import { FormDialog } from "../components/FormDialog";
import { ResourceTable } from "../components/ResourceTable";
import { useResourceDelete } from "../hooks/useResourceDelete";
import { useResourceList } from "../hooks/useResourceList";
import {
  RoutineProfileCreateForm,
  type RoutineProfileCreateBody,
} from "./RoutineProfileCreateForm";

export function RoutineProfilesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [apparatus, setApparatus] = useState("");
  const [dialog, setDialog] = useState<{ row: RoutineProfileRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // Reused from the scoring screen — resolves the gymnast-or-group name pair.
  const { gymnasts, groups, error: namesError } = useCompetitorNames();

  const ownerName = (p: RoutineProfileRead): string => {
    if (p.gymnast_id != null) {
      const g = gymnasts.find((g) => g.id === p.gymnast_id);
      return g ? `${g.first_name} ${g.last_name}` : `Gymnast #${p.gymnast_id}`;
    }
    const grp = groups.find((g) => g.id === p.group_id);
    return grp ? grp.name : `Group #${p.group_id}`;
  };

  const list = useResourceList<RoutineProfileRead>({
    queryKey: ["routine-profiles", apparatus],
    fetchRows: async () => {
      const { data, error } = await client.GET("/routine-profiles/", {
        params: { query: apparatus === "" ? {} : { apparatus: apparatus as Apparatus } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    search,
    searchText: (p) => `${ownerName(p)} ${p.apparatus} ${p.level}`,
  });

  const saveMutation = useMutation({
    mutationFn: async (body: RoutineProfileCreateBody) => {
      const { data, error } = await client.POST("/routine-profiles/", { body });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      clearDeleteError();
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["routine-profiles"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const {
    confirmDelete,
    error: deleteError,
    clearError: clearDeleteError,
  } = useResourceDelete<RoutineProfileRead>({
    queryKey: ["routine-profiles"],
    describe: (p) =>
      `Delete the ${labelize(p.apparatus)} profile for ${ownerName(p)}? Routine music will fall back to none.`,
    remove: async (p) => {
      const { error } = await client.DELETE("/routine-profiles/{profile_id}", {
        params: { path: { profile_id: p.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Routine profiles</h1>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New routine profile
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
          Apparatus
          <select
            aria-label="Apparatus filter"
            value={apparatus}
            onChange={(e) => {
              clearDeleteError();
              setApparatus(e.target.value);
            }}
            className="ml-2 rounded border border-gray-300 p-1"
          >
            <option value="">— all —</option>
            {APPARATUS.map((a) => (
              <option key={a} value={a}>
                {labelize(a)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ErrorBanner message={list.error ?? deleteError ?? namesError?.message ?? null} />
      {list.loaded && (
        <ResourceTable
          rows={list.rows}
          columns={[
            { header: "Owner", render: (p) => ownerName(p) },
            { header: "Apparatus", render: (p) => labelize(p.apparatus) },
            { header: "Level", render: (p) => labelize(p.level) },
            { header: "Music URL", render: (p) => p.music_url ?? "—" },
          ]}
          rowLabel={(p) => `${ownerName(p)} ${labelize(p.apparatus)}`}
          onEdit={(p) => {
            setFormError(null);
            setDialog({ row: p });
          }}
          onDelete={confirmDelete}
          emptyMessage="No routine profiles yet."
        />
      )}
      <FormDialog
        open={dialog !== null}
        title={dialog?.row ? "Edit routine profile" : "New routine profile"}
        onClose={() => setDialog(null)}
      >
        {dialog && !dialog.row && (
          <RoutineProfileCreateForm
            gymnasts={gymnasts}
            groups={groups}
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
