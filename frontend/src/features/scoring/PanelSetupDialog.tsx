import { useState } from "react";
import type { JudgeRead } from "../../api/types";
import { PANEL_SLOTS, type PanelAssignment, type PanelSlot } from "./panel-storage";

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
    if (open) setDraft(value);
  }
  if (!open) return null;

  const E_SLOTS: PanelSlot[] = ["E1", "E2", "E3", "E4"];

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
    const eJudgeIds = E_SLOTS.map((slot) => draft[slot]).filter(
      (id): id is number => id !== undefined,
    );
    const hasDuplicate = new Set(eJudgeIds).size !== eJudgeIds.length;
    if (hasDuplicate) {
      setError("The same judge can't sit in two Execution slots.");
      return;
    }
    onSave(draft);
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/30">
      <div className="w-96 rounded border border-gray-200 bg-white p-4 shadow-lg">
        <h2 className="mb-2 text-lg font-semibold">Judge panel for this meet</h2>
        <p className="mb-3 text-xs text-gray-500">
          Set once when the meet starts; every save attributes scores to these judges.
          The D judge covers both D-Body and D-App.
        </p>
        <div className="grid grid-cols-[3rem_1fr] items-center gap-2">
          {PANEL_SLOTS.map((slot) => (
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
