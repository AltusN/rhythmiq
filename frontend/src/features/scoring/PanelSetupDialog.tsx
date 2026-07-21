import { useState } from "react";
import type { JudgeRead } from "../../api/types";
import type { Band } from "../../lib/score-math";
import {
  SLOTS_BY_BAND,
  SLOT_CONFLICT_GROUPS,
  type PanelAssignment,
  type PanelSlot,
} from "./panel-storage";

const BAND_HEADINGS: Record<Band, string> = {
  "1-3": "Levels 1–3 — one final mark out of 13",
  "4-7": "Levels 4–7 — two Difficulty (Body) judges, two Execution",
  "8+": "Levels 8+ — full FIG panel",
};

const BANDS: Band[] = ["1-3", "4-7", "8+"];

// Keyed by the FIRST slot of each SLOT_CONFLICT_GROUPS group (DB1, A1, E1) -- the error
// message below looks the group's label up via `group[0]`. If a group's slot order ever
// changes, add the new leading slot here (a missing key would render "two undefined slots").
const CONFLICT_LABELS: Record<string, string> = {
  DB1: "Difficulty (Body)",
  A1: "Artistry",
  E1: "Execution",
};

export function PanelSetupDialog({
  open,
  value,
  judges,
  onSave,
  onClose,
}: {
  open: boolean;
  value: PanelAssignment;
  judges: JudgeRead[];
  onSave: (panel: PanelAssignment) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<PanelAssignment>(value);
  const [wasOpen, setWasOpen] = useState(open);
  const [error, setError] = useState<string | null>(null);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setDraft(value);
      setError(null);
    }
  }
  if (!open) return null;

  const setSlot = (slot: PanelSlot, judgeId: string) => {
    setError(null);
    setDraft((d) => {
      const next = { ...d };
      if (judgeId === "") delete next[slot];
      else next[slot] = Number(judgeId);
      return next;
    });
  };

  const handleSave = () => {
    // Slots in the same group write to the same API panel, and JudgeScore is unique on
    // (routine, judge, panel) — a duplicate here would fail at save time, mid-meet.
    for (const group of SLOT_CONFLICT_GROUPS) {
      const ids = group
        .map((slot) => draft[slot])
        .filter((id): id is number => id !== undefined);
      if (new Set(ids).size !== ids.length) {
        setError(
          `The same judge can't sit in two ${CONFLICT_LABELS[group[0]]} slots.`,
        );
        return;
      }
    }
    onSave(draft);
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/30">
      <div className="w-96 rounded border border-gray-200 bg-white p-4 shadow-lg">
        <h2 className="mb-2 text-lg font-semibold">Judge panel for this meet</h2>
        <p className="mb-3 text-xs text-gray-500">
          Set once when the meet starts; every save attributes scores to these judges.
          A meet can span several levels, so fill in the bands you are running. The 8+
          D judge covers both D-Body and D-App.
        </p>
        {BANDS.map((band) => (
          <div key={band} className="mb-3">
            <h3 className="mb-1 text-xs font-semibold uppercase text-gray-500">
              {BAND_HEADINGS[band]}
            </h3>
            <div className="grid grid-cols-[3rem_1fr] items-center gap-2">
              {SLOTS_BY_BAND[band].map((slot) => (
                <label key={slot} className="contents text-sm">
                  <span className="text-xs font-semibold uppercase">{slot}</span>
                  <select
                    aria-label={slot}
                    value={draft[slot] ?? ""}
                    onChange={(e) => setSlot(slot, e.target.value)}
                    className="rounded border border-gray-300 p-1"
                  >
                    <option value="">— unassigned —</option>
                    {judges.map((j) => (
                      <option key={j.id} value={j.id}>
                        {j.first_name} {j.last_name}
                        {j.country_code ? ` (${j.country_code})` : ""}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          </div>
        ))}
        {error && (
          <p role="alert" className="mt-2 text-xs text-red-700">
            {error}
          </p>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded border border-gray-300 px-3 py-1 text-sm">
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white"
          >
            Save panel
          </button>
        </div>
      </div>
    </div>
  );
}
