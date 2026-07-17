import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { toNum } from "../../api/client";
import type {
  Apparatus,
  JudgeScoreRead,
  MeetEntryRead,
  Panel,
  RoutineRead,
} from "../../api/types";
import { computePreview, isEOnlyLevel } from "../../lib/score-math";
import type { PanelAssignment } from "./panel-storage";
import type { BoxDef, BoxKey } from "./save-diff";
import { saveScores, type SaveScoresResult } from "./save-scores";

const BOX_LABELS: Record<BoxKey, string> = {
  dBody: "D-Body",
  dApp: "D-App",
  a: "Artistry",
  e1: "E1",
  e2: "E2",
  e3: "E3",
  e4: "E4",
};

const E_KEYS: BoxKey[] = ["e1", "e2", "e3", "e4"];
const CAPPED: ReadonlySet<BoxKey> = new Set(["a", "e1", "e2", "e3", "e4"]);

type FormValues = Record<BoxKey | "penalty", string>;

export function boxesFor(panel: PanelAssignment): BoxDef[] {
  return [
    { key: "dBody", panel: "difficulty_body" as Panel, judgeId: panel.D },
    { key: "dApp", panel: "difficulty_apparatus" as Panel, judgeId: panel.D },
    { key: "a", panel: "artistry" as Panel, judgeId: panel.A },
    { key: "e1", panel: "execution" as Panel, judgeId: panel.E1 },
    { key: "e2", panel: "execution" as Panel, judgeId: panel.E2 },
    { key: "e3", panel: "execution" as Panel, judgeId: panel.E3 },
    { key: "e4", panel: "execution" as Panel, judgeId: panel.E4 },
  ];
}

function parseBox(s: string): number | undefined {
  const t = s.trim();
  return t === "" ? undefined : Number(t);
}

/** "" ok; else numeric, ≥0, 0.05 steps, ≤10 for E/A boxes. Returns error or null. */
function validateBox(key: BoxKey | "penalty", s: string): string | null {
  const t = s.trim();
  if (t === "") return null;
  const n = Number(t);
  if (Number.isNaN(n)) return "Not a number";
  if (n < 0) return "Must be ≥ 0";
  if (Math.round(n * 100) % 5 !== 0) return "Use 0.05 steps";
  if (key !== "penalty" && CAPPED.has(key) && n > 10) return "Max 10";
  return null;
}

export function ScoreForm({
  entry,
  apparatus,
  routine,
  existingScores,
  panel,
  penaltyLocked,
  meetLocked,
  onSaved,
}: {
  entry: MeetEntryRead;
  apparatus: Apparatus;
  routine: RoutineRead | undefined;
  existingScores: JudgeScoreRead[];
  panel: PanelAssignment;
  penaltyLocked: boolean;
  meetLocked: boolean;
  onSaved: (result: SaveScoresResult, next: boolean) => void;
}) {
  const boxes = boxesFor(panel);
  const eOnly = isEOnlyLevel(entry.level);
  const visibleBoxes = eOnly
    ? boxes.filter((b) => E_KEYS.includes(b.key))
    : boxes;

  const defaultValues = useMemo<FormValues>(() => {
    const values = {
      dBody: "", dApp: "", a: "", e1: "", e2: "", e3: "", e4: "",
      penalty: routine ? String(toNum(routine.penalty) || "") : "",
    } as FormValues;
    for (const box of boxes) {
      if (box.judgeId === undefined) continue;
      const existing = existingScores.find(
        (s) => s.judge_id === box.judgeId && s.panel === box.panel,
      );
      if (existing) values[box.key] = String(toNum(existing.value));
    }
    return values;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { register, handleSubmit, watch, setError, formState } =
    useForm<FormValues>({ defaultValues });
  const [saving, setSaving] = useState(false);

  const watched = watch();
  const preview = computePreview({
    dBody: eOnly ? undefined : parseBox(watched.dBody),
    dApp: eOnly ? undefined : parseBox(watched.dApp),
    artistry: eOnly ? undefined : parseBox(watched.a),
    eScores: E_KEYS.map((k) => parseBox(watched[k])).filter(
      (v): v is number => v !== undefined,
    ),
    penalty: parseBox(watched.penalty),
  });

  const submit = (next: boolean) =>
    handleSubmit(async (values) => {
      setSaving(true);
      try {
        const result = await saveScores({
          routineId: routine?.id,
          entryId: entry.id,
          apparatus,
          boxes: visibleBoxes,
          existing: existingScores.map((s) => ({
            id: s.id,
            judge_id: s.judge_id,
            panel: s.panel,
            value: toNum(s.value),
          })),
          values: Object.fromEntries(
            visibleBoxes.map((b) => [b.key, parseBox(values[b.key])]),
          ),
          penalty: penaltyLocked ? undefined : (parseBox(values.penalty) ?? 0),
          currentPenalty: routine ? toNum(routine.penalty) : 0,
        });
        for (const [key, message] of Object.entries(result.boxErrors)) {
          setError(key as BoxKey | "penalty", { type: "server", message });
        }
        onSaved(result, next && Object.keys(result.boxErrors).length === 0);
      } finally {
        setSaving(false);
      }
    });

  const boxInput = (key: BoxKey | "penalty", disabled: boolean, title?: string) => (
    <div key={key}>
      <label
        htmlFor={`box-${key}`}
        className="block text-xs font-semibold uppercase text-gray-500"
      >
        {key === "penalty" ? "Penalty" : BOX_LABELS[key]}
      </label>
      <input
        id={`box-${key}`}
        inputMode="decimal"
        disabled={disabled || meetLocked}
        title={title}
        placeholder={disabled ? "—" : "0.00"}
        {...register(key, { validate: (v) => validateBox(key, v) ?? true })}
        className="w-20 rounded border border-gray-300 p-1 text-center text-lg disabled:bg-gray-100"
      />
      {formState.errors[key] && (
        <p className="mt-1 w-20 text-xs text-red-700">
          {formState.errors[key]?.message || "Invalid"}
        </p>
      )}
    </div>
  );

  const fmt = (n: number) => n.toFixed(2);

  return (
    <form onSubmit={submit(true)}>
      <div className="flex flex-wrap items-start gap-4">
        {visibleBoxes.map((box) =>
          boxInput(
            box.key,
            box.judgeId === undefined,
            box.judgeId === undefined ? "No judge assigned to this slot" : undefined,
          ),
        )}
        {boxInput(
          "penalty",
          penaltyLocked,
          penaltyLocked
            ? "This routine has itemized penalty records; the total is managed by them."
            : undefined,
        )}
      </div>
      <div className="mt-4 flex gap-6 rounded border border-dashed border-gray-300 p-2 text-sm">
        {!eOnly && <span>D: <strong>{fmt(preview.d)}</strong></span>}
        {!eOnly && <span>A: <strong>{fmt(preview.a)}</strong></span>}
        <span>E: <strong>{fmt(preview.e)}</strong></span>
        <span>Penalty: <strong>−{fmt(preview.penalty)}</strong></span>
        <span className="ml-auto">Total: <strong>{fmt(preview.total)}</strong></span>
      </div>
      {!meetLocked && (
        <div className="mt-4 flex items-center gap-2">
          <button
            type="submit"
            disabled={saving}
            className="rounded bg-blue-600 px-3 py-1 text-sm font-bold text-white hover:bg-blue-700"
          >
            Save &amp; next
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={() => void submit(false)()}
            className="rounded border border-gray-300 bg-white px-3 py-1 text-sm"
          >
            Save
          </button>
        </div>
      )}
    </form>
  );
}
