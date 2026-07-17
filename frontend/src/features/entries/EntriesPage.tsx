import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { apiDetail, client } from "../../api/client";
import type { MeetRead } from "../../api/types";
import { ErrorBanner } from "../../components/ErrorBanner";
import { isMeetLocked, labelize } from "../../lib/domain";
import { useCompetitorNames } from "../../lib/useCompetitorNames";
import { EntryCreateForm } from "./EntryCreateForm";

export function EntriesPage() {
  const meet = useOutletContext<MeetRead>();
  const queryClient = useQueryClient();
  const locked = isMeetLocked(meet.status);
  const [showForm, setShowForm] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const { nameFor, gymnasts, groups } = useCompetitorNames();

  const { data: entries, error, isPending } = useQuery({
    queryKey: ["entries", meet.id],
    queryFn: async () => {
      const { data, error } = await client.GET("/meet-entries/", {
        params: { query: { meet_id: meet.id } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (entryId: number) => {
      const { error } = await client.DELETE("/meet-entries/{entry_id}", {
        params: { path: { entry_id: entryId } },
      });
      if (error) throw new Error(apiDetail(error));
    },
    onSuccess: () => {
      setDeleteError(null);
      queryClient.invalidateQueries({ queryKey: ["entries", meet.id] });
    },
    onError: (e: Error) => setDeleteError(e.message),
  });

  if (isPending) return <p>Loading…</p>;
  if (error) return <ErrorBanner message={error.message} />;

  return (
    <div>
      {locked ? (
        <p className="mb-3 text-sm text-gray-500">
          This meet is {labelize(meet.status)} — entries are read-only.
        </p>
      ) : (
        <button
          onClick={() => setShowForm((s) => !s)}
          className="mb-3 rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          Add entry
        </button>
      )}
      {showForm && !locked && (
        <EntryCreateForm
          meetId={meet.id}
          gymnasts={gymnasts}
          groups={groups}
          onCreated={() => setShowForm(false)}
        />
      )}
      <ErrorBanner message={deleteError} />
      <table className="w-full rounded border border-gray-200 bg-white text-sm">
        <thead>
          <tr className="text-left text-xs uppercase text-gray-500">
            <th className="p-2">Bib</th>
            <th className="p-2">Competitor</th>
            <th className="p-2">Level</th>
            <th className="p-2">Age group</th>
            <th className="p-2">Fee paid</th>
            <th className="p-2"></th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id} className="border-t border-gray-100">
              <td className="p-2">{entry.bib_number}</td>
              <td className="p-2">{nameFor(entry)}</td>
              <td className="p-2">{labelize(entry.level)}</td>
              <td className="p-2">{entry.age_group}</td>
              <td className="p-2">{entry.entry_fee_paid ? "yes" : "no"}</td>
              <td className="p-2 text-right">
                {!locked && (
                  <button
                    onClick={() => {
                      if (window.confirm(`Delete entry (bib ${entry.bib_number})? Its routines and scores go with it.`)) {
                        deleteMutation.mutate(entry.id);
                      }
                    }}
                    className="text-red-700 hover:underline"
                  >
                    Delete
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
