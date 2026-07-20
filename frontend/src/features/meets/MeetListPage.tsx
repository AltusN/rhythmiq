import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { apiDetail, client } from "../../api/client";
import type { components } from "../../api/schema";
import type { DistrictRead, MeetRead } from "../../api/types";
import { ErrorBanner } from "../../components/ErrorBanner";
import { labelize, meetStatusBadgeClass } from "../../lib/domain";
import { FormDialog } from "../admin/components/FormDialog";
import { useResourceDelete } from "../admin/hooks/useResourceDelete";
import { MeetForm, type MeetBody } from "./MeetForm";

export function MeetListPage() {
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<{ row: MeetRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const meetsQuery = useQuery({
    queryKey: ["meets"],
    queryFn: async () => {
      const { data, error } = await client.GET("/meets/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const districtsQuery = useQuery({
    queryKey: ["districts"],
    queryFn: async () => {
      const { data, error } = await client.GET("/districts/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });
  const districts: DistrictRead[] = districtsQuery.data ?? [];

  const saveMutation = useMutation({
    mutationFn: async (body: MeetBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/meets/{meet_id}", {
          params: { path: { meet_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      // MeetCreate.status is required by the generated type (openapi-typescript doesn't
      // treat the backend's server-side `draft` default as optional), but the server
      // already defaults it -- omit it on the wire (see the "status absent from this
      // form" note above) and assert the narrower literal against the generated type.
      const { data, error } = await client.POST("/meets/", {
        body: body as components["schemas"]["MeetCreate"],
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      clearDeleteError();
      // dialog.row is the row this save was editing (undefined for a create) --
      // captured here the same way mutationFn reads it above.
      const editedId = dialog?.row?.id;
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["meets"] });
      if (editedId !== undefined) {
        // MeetShell keys its detail query off useParams' meetId, which is always a
        // string -- match that shape or the invalidation silently won't hit it.
        queryClient.invalidateQueries({ queryKey: ["meet", String(editedId)] });
        // Medal minima live on this same form and feed medal_for_total
        // (app/scoring.py), so an edit here can change every standings row's medal
        // tier, same as editing them from MeetShell's header does.
        queryClient.invalidateQueries({ queryKey: ["standings"] });
      }
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const {
    confirmDelete,
    error: deleteError,
    clearError: clearDeleteError,
  } = useResourceDelete<MeetRead>({
    queryKey: ["meets"],
    // Meet deletes cascade to entries and routines, but are rejected (409) while
    // in_progress or completed — a completed meet is the historical record.
    describe: (m) =>
      `Delete "${m.name}"? This also deletes its entries and routines. Meets that are in progress or completed cannot be deleted.`,
    remove: async (m) => {
      const { error } = await client.DELETE("/meets/{meet_id}", {
        params: { path: { meet_id: m.id } },
      });
      if (error) throw new Error(apiDetail(error));
      // The meet is gone server-side -- drop its cached detail entry rather than
      // leaving stale data behind for a MeetShell that never gets the chance to
      // refetch (the meet no longer exists to invalidate-and-refetch against).
      queryClient.removeQueries({ queryKey: ["meet", String(m.id)] });
    },
  });

  if (meetsQuery.isPending) return <p>Loading…</p>;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Meets</h1>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New meet
        </button>
      </div>
      <ErrorBanner
        message={
          meetsQuery.error?.message ??
          districtsQuery.error?.message ??
          deleteError ??
          null
        }
      />
      <ul className="divide-y divide-gray-200 rounded border border-gray-200 bg-white">
        {(meetsQuery.data ?? []).map((meet) => (
          // The Link covers only the meet text: a <button> cannot be nested inside an
          // <a>, and the click would propagate into navigation.
          <li key={meet.id} className="flex items-center justify-between px-4 py-3">
            <Link to={`/meets/${meet.id}`} className="flex-1 hover:underline">
              <span>
                {meet.name}{" "}
                <span className="text-sm text-gray-500">
                  {meet.location} · {meet.start_date}
                </span>
              </span>
            </Link>
            <span
              className={`ml-3 rounded px-2 py-1 text-xs ${meetStatusBadgeClass(meet.status)}`}
            >
              {labelize(meet.status)}
            </span>
            <button
              type="button"
              aria-label={`Edit ${meet.name}`}
              onClick={() => {
                setFormError(null);
                setDialog({ row: meet });
              }}
              className="ml-3 rounded border border-gray-300 px-2 py-0.5 text-xs"
            >
              Edit
            </button>
            <button
              type="button"
              aria-label={`Delete ${meet.name}`}
              onClick={() => confirmDelete(meet)}
              className="ml-2 rounded border border-gray-300 px-2 py-0.5 text-xs text-red-700"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
      <FormDialog
        open={dialog !== null}
        title={dialog?.row ? "Edit meet" : "New meet"}
        onClose={() => setDialog(null)}
      >
        {dialog && (
          <MeetForm
            key={dialog.row?.id ?? "new"}
            initial={dialog.row}
            districts={districts}
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
