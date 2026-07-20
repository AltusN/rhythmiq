import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { NavLink, Outlet, useParams } from "react-router-dom";
import { apiDetail, client } from "../../api/client";
import type { DistrictRead, MeetStatus } from "../../api/types";
import { ErrorBanner } from "../../components/ErrorBanner";
import {
  labelize,
  MEET_STATUS_TRANSITIONS,
  meetStatusBadgeClass,
  STATUS_ACTION_LABELS,
} from "../../lib/domain";
import { FormDialog } from "../admin/components/FormDialog";
import { MeetForm, type MeetBody } from "./MeetForm";

const CONFIRM_TARGETS = new Set<MeetStatus>(["completed", "cancelled"]);
const TABS = ["scoring", "entries", "standings"] as const;

export function MeetShell() {
  const { meetId } = useParams();
  const queryClient = useQueryClient();
  const [statusError, setStatusError] = useState<string | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [detailsError, setDetailsError] = useState<string | null>(null);

  const { data: meet, error, isPending } = useQuery({
    queryKey: ["meet", meetId],
    queryFn: async () => {
      const { data, error } = await client.GET("/meets/{meet_id}", {
        params: { path: { meet_id: Number(meetId) } },
      });
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

  const statusMutation = useMutation({
    mutationFn: async (status: MeetStatus) => {
      const { data, error } = await client.PATCH("/meets/{meet_id}", {
        params: { path: { meet_id: Number(meetId) } },
        body: { status },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setStatusError(null);
      queryClient.invalidateQueries({ queryKey: ["meet", meetId] });
      queryClient.invalidateQueries({ queryKey: ["standings"] });
    },
    onError: (e: Error) => setStatusError(e.message),
  });

  const detailsMutation = useMutation({
    mutationFn: async (body: MeetBody) => {
      const { data, error } = await client.PATCH("/meets/{meet_id}", {
        params: { path: { meet_id: Number(meetId) } },
        body,
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setDetailsError(null);
      setDetailsOpen(false);
      queryClient.invalidateQueries({ queryKey: ["meet", meetId] });
      queryClient.invalidateQueries({ queryKey: ["meets"] });
      // Medal minima live on this same form and feed medal_for_total (app/scoring.py),
      // so an edit here can change every standings row's medal tier.
      queryClient.invalidateQueries({ queryKey: ["standings"] });
    },
    onError: (e: Error) => setDetailsError(e.message),
  });

  if (isPending) return <p>Loading…</p>;
  if (error) return <ErrorBanner message={error.message} />;

  const transition = (target: MeetStatus) => {
    if (CONFIRM_TARGETS.has(target)) {
      const verb = target === "completed" ? "complete" : "cancel";
      const warning =
        target === "completed"
          ? "Completing freezes all scores and cannot be undone."
          : "Cancelling cannot be undone.";
      if (!window.confirm(`Really ${verb} "${meet.name}"? ${warning}`)) return;
    }
    statusMutation.mutate(target);
  };

  return (
    <div>
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{meet.name}</h1>
          <p className="text-sm text-gray-500">
            {meet.location} · {meet.start_date} – {meet.end_date} ·{" "}
            <span className={`rounded px-2 py-0.5 ${meetStatusBadgeClass(meet.status)}`}>
              {labelize(meet.status)}
            </span>
          </p>
        </div>
        <div className="flex gap-2">
          {MEET_STATUS_TRANSITIONS[meet.status].map((target) => (
            <button
              key={target}
              onClick={() => transition(target)}
              disabled={statusMutation.isPending}
              className="rounded border border-gray-300 bg-white px-3 py-1 text-sm hover:bg-gray-50"
            >
              {STATUS_ACTION_LABELS[target]}
            </button>
          ))}
          <button
            type="button"
            onClick={() => {
              setDetailsError(null);
              setDetailsOpen(true);
            }}
            className="rounded border border-gray-300 px-3 py-1 text-sm"
          >
            Edit details
          </button>
        </div>
      </header>
      <ErrorBanner message={statusError} />
      <nav className="mb-4 flex gap-4 border-b border-gray-200">
        {TABS.map((tab) => (
          <NavLink
            key={tab}
            to={tab}
            className={({ isActive }) =>
              `border-b-2 px-1 pb-2 capitalize ${
                isActive
                  ? "border-blue-600 font-semibold text-blue-700"
                  : "border-transparent text-gray-600 hover:text-gray-900"
              }`
            }
          >
            {tab}
          </NavLink>
        ))}
      </nav>
      <Outlet context={meet} />
      <FormDialog
        open={detailsOpen}
        title="Edit meet"
        onClose={() => setDetailsOpen(false)}
      >
        {detailsOpen && (
          <MeetForm
            initial={meet}
            districts={districts}
            pending={detailsMutation.isPending}
            error={detailsError}
            onSubmit={(body) => detailsMutation.mutate(body)}
            onCancel={() => setDetailsOpen(false)}
          />
        )}
      </FormDialog>
    </div>
  );
}
