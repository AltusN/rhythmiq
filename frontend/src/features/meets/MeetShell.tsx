import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { NavLink, Outlet, useParams } from "react-router-dom";
import { apiDetail, client } from "../../api/client";
import type { MeetStatus } from "../../api/types";
import { ErrorBanner } from "../../components/ErrorBanner";
import {
  labelize,
  MEET_STATUS_TRANSITIONS,
  STATUS_ACTION_LABELS,
} from "../../lib/domain";

const CONFIRM_TARGETS = new Set<MeetStatus>(["completed", "cancelled"]);
const TABS = ["scoring", "entries", "standings"] as const;

export function MeetShell() {
  const { meetId } = useParams();
  const queryClient = useQueryClient();
  const [statusError, setStatusError] = useState<string | null>(null);

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
            <span className="rounded bg-gray-100 px-2 py-0.5">
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
    </div>
  );
}
