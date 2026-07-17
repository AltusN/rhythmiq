import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { apiDetail, client, toNum } from "../../api/client";
import type { Apparatus, MeetRead } from "../../api/types";
import { ErrorBanner } from "../../components/ErrorBanner";
import { isMeetLocked, labelize } from "../../lib/domain";
import { isEOnlyLevel } from "../../lib/score-math";
import { useCompetitorNames } from "../../lib/useCompetitorNames";
import { CompetitorList } from "./CompetitorList";
import { nextUnscored } from "./next-unscored";
import {
  loadPanel,
  savePanel,
  type PanelAssignment,
  type PanelSlot,
} from "./panel-storage";
import { PanelSetupDialog } from "./PanelSetupDialog";
import { ScoreForm } from "./ScoreForm";

/** The minimum viable panel; E3/E4 legitimately stay empty on small panels. */
function missingRequiredSlots(panel: PanelAssignment, level: string): PanelSlot[] {
  const required: PanelSlot[] = isEOnlyLevel(level)
    ? ["E1", "E2"]
    : ["D", "A", "E1", "E2"];
  return required.filter((slot) => panel[slot] === undefined);
}

export function ScoringPage() {
  const meet = useOutletContext<MeetRead>();
  const queryClient = useQueryClient();
  const meetLocked = isMeetLocked(meet.status);

  const [level, setLevel] = useState("");
  const [ageGroup, setAgeGroup] = useState("");
  const [apparatus, setApparatus] = useState<Apparatus>("hoop");
  const [search, setSearch] = useState("");
  const [selectedEntryId, setSelectedEntryId] = useState<number | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [panel, setPanel] = useState<PanelAssignment>(() => loadPanel(meet.id));

  const { nameFor, error: namesError } = useCompetitorNames();

  const entriesQ = useQuery({
    queryKey: ["entries", meet.id, level, ageGroup],
    queryFn: async () => {
      const { data, error } = await client.GET("/meet-entries/", {
        params: {
          query: {
            meet_id: meet.id,
            level: level || undefined,
            age_group: ageGroup || undefined,
          },
        },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const judgesQ = useQuery({
    queryKey: ["judges"],
    queryFn: async () => {
      const { data, error } = await client.GET("/judges/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const standingsQ = useQuery({
    queryKey: ["standings", meet.id, "apparatus", apparatus, "", ""],
    queryFn: async () => {
      const { data, error } = await client.GET("/meets/{meet_id}/standings", {
        params: { path: { meet_id: meet.id }, query: { apparatus } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });
  const scoredTotals = new Map<number, string>(
    (standingsQ.data?.rankings ?? []).map((row) => [
      row.entry_id,
      toNum(row.total).toFixed(2),
    ]),
  );

  const entries = entriesQ.data ?? [];
  const selectedEntry = entries.find((e) => e.id === selectedEntryId) ?? null;

  const routinesQ = useQuery({
    queryKey: ["routines", selectedEntryId],
    enabled: selectedEntryId !== null,
    queryFn: async () => {
      const { data, error } = await client.GET("/routines/", {
        params: { query: { entry_id: selectedEntryId! } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });
  const routine = routinesQ.data?.find((r) => r.apparatus === apparatus);

  const scoresQ = useQuery({
    queryKey: ["judge-scores", routine?.id],
    enabled: routine !== undefined,
    queryFn: async () => {
      const { data, error } = await client.GET("/judge-scores/", {
        params: { query: { routine_id: routine!.id } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const penaltyRecordsQ = useQuery({
    queryKey: ["penalty-records", routine?.id],
    enabled: routine !== undefined,
    queryFn: async () => {
      const { data, error } = await client.GET("/penalty-records/", {
        params: { query: { routine_id: routine!.id } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const judgeName = (id: number): string => {
    const j = (judgesQ.data ?? []).find((j) => j.id === id);
    return j ? `${j.first_name} ${j.last_name}` : `#${id}`;
  };
  const slotLabel = (id: number | undefined) =>
    id === undefined ? (
      <span className="text-amber-600">unassigned</span>
    ) : (
      judgeName(id)
    );

  const detailError = routinesQ.error ?? scoresQ.error ?? penaltyRecordsQ.error ?? null;

  const formReady =
    selectedEntry !== null &&
    routinesQ.data !== undefined &&
    (routine === undefined ||
      (scoresQ.data !== undefined && penaltyRecordsQ.data !== undefined));

  // Once the form has been shown for a given entry+apparatus, keep it mounted even if a
  // post-save invalidation makes `routine` transition from undefined to defined (which keys
  // scoresQ/penaltyRecordsQ onto the new routine id and makes them momentarily "loading"
  // again). Swapping to the Loading fallback at that point would unmount ScoreForm and lose
  // its in-progress values/errors -- the data those queries would deliver only matters for
  // the initial mount's default values, which are already set.
  const formKey = selectedEntry !== null ? `${selectedEntry.id}-${apparatus}` : null;
  const [readyFormKey, setReadyFormKey] = useState<string | null>(null);
  useEffect(() => {
    if (formReady && formKey !== null) setReadyFormKey(formKey);
  }, [formReady, formKey]);
  const showForm =
    selectedEntry !== null &&
    formKey !== null &&
    (formReady || readyFormKey === formKey);

  const afterSave = (next: boolean) => {
    queryClient.invalidateQueries({ queryKey: ["routines", selectedEntryId] });
    queryClient.invalidateQueries({ queryKey: ["judge-scores"] });
    queryClient.invalidateQueries({ queryKey: ["penalty-records"] });
    queryClient.invalidateQueries({ queryKey: ["standings", meet.id] });
    if (next) {
      const candidate = nextUnscored(entries, scoredTotals, selectedEntryId);
      if (candidate) setSelectedEntryId(candidate.id);
    }
  };

  return (
    <div className="flex gap-6">
      <CompetitorList
        entries={entries}
        nameFor={nameFor}
        scoredTotals={scoredTotals}
        selectedEntryId={selectedEntryId}
        onSelect={(entry) => setSelectedEntryId(entry.id)}
        search={search}
        onSearchChange={setSearch}
        level={level}
        onLevelChange={(l) => {
          setLevel(l);
          setSelectedEntryId(null);
        }}
        ageGroup={ageGroup}
        onAgeGroupChange={(a) => {
          setAgeGroup(a);
          setSelectedEntryId(null);
        }}
        apparatus={apparatus}
        onApparatusChange={(a) => {
          setApparatus(a as Apparatus);
          setSelectedEntryId(null);
        }}
      />
      <div className="min-w-0 flex-1">
        {entriesQ.error && <ErrorBanner message={entriesQ.error.message} />}
        {namesError && <ErrorBanner message={namesError.message} />}
        {selectedEntry === null && (
          <p className="text-gray-500">Pick a competitor to score.</p>
        )}
        {selectedEntry !== null &&
          !showForm &&
          (detailError ? <ErrorBanner message={detailError.message} /> : <p>Loading…</p>)}
        {selectedEntry !== null && showForm && (
          <div>
            {detailError && <ErrorBanner message={detailError.message} />}
            <h2 className="mb-3 text-lg font-semibold">
              Bib {selectedEntry.bib_number} · {nameFor(selectedEntry)} ·{" "}
              {apparatus} · {labelize(selectedEntry.level)}
            </h2>
            {meetLocked && (
              <p className="mb-3 text-sm text-gray-500">
                This meet is {labelize(meet.status)} — scores are read-only.
              </p>
            )}
            {!meetLocked &&
              missingRequiredSlots(panel, selectedEntry.level).length > 0 && (
                <p className="mb-3 text-sm text-amber-700">
                  Judge slots unassigned:{" "}
                  {missingRequiredSlots(panel, selectedEntry.level).join(", ")}.{" "}
                  <button
                    onClick={() => setPanelOpen(true)}
                    className="underline"
                  >
                    Assign judges…
                  </button>
                </p>
              )}
            <ScoreForm
              key={formKey}
              entry={selectedEntry}
              apparatus={apparatus}
              routine={routine}
              existingScores={scoresQ.data ?? []}
              panel={panel}
              penaltyLocked={(penaltyRecordsQ.data ?? []).length > 0}
              meetLocked={meetLocked}
              onSaved={(_result, next) => afterSave(next)}
            />
            <p className="mt-5 text-xs text-gray-500">
              Panel: D = {slotLabel(panel.D)} · E1 = {slotLabel(panel.E1)} · E2 ={" "}
              {slotLabel(panel.E2)} · E3 = {slotLabel(panel.E3)} · E4 ={" "}
              {slotLabel(panel.E4)} · A = {slotLabel(panel.A)}{" "}
              <button
                onClick={() => setPanelOpen(true)}
                className="text-blue-700 underline"
              >
                change panel…
              </button>
            </p>
          </div>
        )}
        {selectedEntry === null && (
          <button
            onClick={() => setPanelOpen(true)}
            className="mt-2 text-sm text-blue-700 underline"
          >
            Set up judge panel…
          </button>
        )}
      </div>
      <PanelSetupDialog
        open={panelOpen}
        value={panel}
        judges={judgesQ.data ?? []}
        onSave={(p) => {
          savePanel(meet.id, p);
          setPanel(p);
          setPanelOpen(false);
        }}
        onClose={() => setPanelOpen(false)}
      />
    </div>
  );
}
