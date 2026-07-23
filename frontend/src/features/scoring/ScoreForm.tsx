import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { toNum } from "../../api/client";
import type {
  Apparatus,
  JudgeScoreRead,
  MeetEntryRead,
  Panel,
  RoutineRead,
} from "../../api/types";
import {
  computePreview,
  deductionToScore,
  profileForLevel,
  scoreToDeduction,
  type Band,
} from "../../lib/score-math";
import type { PanelAssignment } from "./panel-storage";
import {
  findBoxScore,
  reconcileBoxesWithHistory,
  type BoxDef,
  type BoxKey,
} from "./save-diff";
import { saveScores, type SaveScoresResult } from "./save-scores";

const BOX_LABELS: Record<BoxKey, string> = {
  final1: "Final 1",
  final2: "Final 2",
  final3: "Final 3",
  final4: "Final 4",
  dBody1: "D-Body 1",
  dBody2: "D-Body 2",
  dApp: "D-App",
  a1: "Artistry 1",
  a2: "Artistry 2",
  e1: "E1",
  e2: "E2",
  e3: "E3",
  e4: "E4",
};

export const E_BOX_KEYS: BoxKey[] = ["e1", "e2", "e3", "e4"];

/** Per-box ceiling; undefined = uncapped, mirroring ck_judge_score_panel_value_cap. */
const BOX_MAX: Partial<Record<BoxKey | "penalty", number>> = {
  final1: 13,
  final2: 13,
  final3: 13,
  final4: 13,
  a1: 10,
  a2: 10,
  e1: 10,
  e2: 10,
  e3: 10,
  e4: 10,
};

type FormValues = Record<BoxKey | "penalty", string>;

const EMPTY_VALUES: FormValues = {
  final1: "",
  final2: "",
  final3: "",
  final4: "",
  dBody1: "",
  dBody2: "",
  dApp: "",
  a1: "",
  a2: "",
  e1: "",
  e2: "",
  e3: "",
  e4: "",
  penalty: "",
};

/**
 * The boxes to render for `band`, already filtered — there is no separate "visible"
 * subset. Levels 4-7 have TWO D-Body judges and no D-App at all; levels 8+ have one
 * D judge covering both difficulty panels. See the spec's "Deliberate asymmetry".
 */
export function boxesFor(panel: PanelAssignment, band: Band): BoxDef[] {
  if (band === "1-3") {
    return [
      { key: "final1", panel: "final" as Panel, judgeId: panel.F1 },
      { key: "final2", panel: "final" as Panel, judgeId: panel.F2 },
      { key: "final3", panel: "final" as Panel, judgeId: panel.F3 },
      { key: "final4", panel: "final" as Panel, judgeId: panel.F4 },
    ];
  }
  if (band === "4-7") {
    return [
      { key: "dBody1", panel: "difficulty_body" as Panel, judgeId: panel.DB1 },
      { key: "dBody2", panel: "difficulty_body" as Panel, judgeId: panel.DB2 },
      { key: "e1", panel: "execution" as Panel, judgeId: panel.E1 },
      { key: "e2", panel: "execution" as Panel, judgeId: panel.E2 },
    ];
  }
  return [
    { key: "dBody1", panel: "difficulty_body" as Panel, judgeId: panel.D },
    { key: "dApp", panel: "difficulty_apparatus" as Panel, judgeId: panel.D },
    { key: "a1", panel: "artistry" as Panel, judgeId: panel.A1 },
    { key: "a2", panel: "artistry" as Panel, judgeId: panel.A2 },
    { key: "e1", panel: "execution" as Panel, judgeId: panel.E1 },
    { key: "e2", panel: "execution" as Panel, judgeId: panel.E2 },
    { key: "e3", panel: "execution" as Panel, judgeId: panel.E3 },
    { key: "e4", panel: "execution" as Panel, judgeId: panel.E4 },
  ];
}

// Unparseable text reads as "empty" so the live preview never shows NaN. Saves can't
// misread garbage as a cleared box (=> DELETE): submit is gated by validateBox, which
// rejects non-numbers before values reach the save diff.
function parseBox(s: string): number | undefined {
  const t = s.trim();
  if (t === "") return undefined;
  const n = Number(t);
  return Number.isNaN(n) ? undefined : n;
}

/**
 * "" ok; else numeric, >= 0, 0.05 steps, within the box's ceiling.
 *
 * E boxes hold DEDUCTIONS, which share Execution's 0-10 range: the stored score is
 * 10 - deduction, so a deduction outside 0-10 produces a value the DB rejects. Bound it
 * here rather than only at the API.
 */
function validateBox(key: BoxKey | "penalty", s: string): string | null {
  const t = s.trim();
  if (t === "") return null;
  const n = Number(t);
  if (Number.isNaN(n)) return "Not a number";
  if (n < 0) return "Must be ≥ 0";
  if (Math.round(n * 100) % 5 !== 0) return "Use 0.05 steps";
  const max = BOX_MAX[key];
  if (key !== "penalty" && max !== undefined && n > max) return `Max ${max}`;
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
  onDirtyChange,
}: {
  entry: MeetEntryRead;
  apparatus: Apparatus;
  routine: RoutineRead | undefined;
  existingScores: JudgeScoreRead[];
  panel: PanelAssignment;
  penaltyLocked: boolean;
  meetLocked: boolean;
  onSaved: (result: SaveScoresResult, next: boolean) => void;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const band = profileForLevel(entry.level).band;
  // Rebind boxes to the judges who actually gave this routine's marks, so a scored
  // routine shows its historical record rather than the current panel seating (which may
  // have moved, or never matched seeded/imported data). See reconcileBoxesWithHistory.
  const boxes = reconcileBoxesWithHistory(boxesFor(panel, band), existingScores);

  const defaultValues = useMemo<FormValues>(() => {
    const values: FormValues = {
      ...EMPTY_VALUES,
      penalty:
        routine && toNum(routine.penalty) !== 0
          ? toNum(routine.penalty).toFixed(2)
          : "",
    };
    for (const box of boxes) {
      if (box.judgeId === undefined) continue;
      const existing = findBoxScore(box, existingScores);
      if (!existing) continue;
      const stored = toNum(existing.value);
      // Load direction of the E round trip: the API stores an execution score, the
      // judge typed a deduction. Without this inversion they would reopen a routine and
      // see 8.50 in the box where they entered 1.50.
      values[box.key] = E_BOX_KEYS.includes(box.key)
        ? scoreToDeduction(stored).toFixed(2)
        : stored.toFixed(2);
    }
    return values;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { register, handleSubmit, watch, setError, setFocus, reset, formState } =
    useForm<FormValues>({ defaultValues });
  const [saving, setSaving] = useState(false);

  const { isDirty } = formState;
  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  // Mount-only, like defaultValues: the component is keyed by (entry, apparatus) in
  // ScoringPage, so every competitor/apparatus switch is a fresh mount.
  useEffect(() => {
    if (meetLocked) return;
    const first = boxes.find((b) => b.judgeId !== undefined);
    if (first) setFocus(first.key);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [justSaved, setJustSaved] = useState(false);
  useEffect(() => {
    if (!justSaved) return;
    const timer = setTimeout(() => setJustSaved(false), 2000);
    return () => clearTimeout(timer);
  }, [justSaved]);
  useEffect(() => {
    // only user edits clear the indicator ("change"); programmatic resets don't
    const sub = watch((_, { type }) => {
      if (type === "change") setJustSaved(false);
    });
    return () => sub.unsubscribe();
  }, [watch]);

  const watched = watch();
  const preview = computePreview({
    band,
    // Marks are grouped by panel here exactly as the backend groups them, so the
    // two-DB-judge and four-E-judge cases reduce through the same code on both sides.
    dBodyScores: [parseBox(watched.dBody1), parseBox(watched.dBody2)].filter(
      (v): v is number => v !== undefined,
    ),
    dAppScores: [parseBox(watched.dApp)].filter((v): v is number => v !== undefined),
    artistryScores: [parseBox(watched.a1), parseBox(watched.a2)].filter(
      (v): v is number => v !== undefined,
    ),
    // The summary line shows the E SCORE, not the deduction total — it is what feeds
    // the total, and the total is what the scorer is checking.
    eScores: E_BOX_KEYS.map((k) => parseBox(watched[k]))
      .filter((v): v is number => v !== undefined)
      .map(deductionToScore),
    finalScores: [
      parseBox(watched.final1),
      parseBox(watched.final2),
      parseBox(watched.final3),
      parseBox(watched.final4),
    ].filter((v): v is number => v !== undefined),
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
          boxes,
          existing: existingScores.map((s) => ({
            id: s.id,
            judge_id: s.judge_id,
            panel: s.panel,
            value: toNum(s.value),
          })),
          values: Object.fromEntries(
            boxes.map((b) => {
              const raw = parseBox(values[b.key]);
              // Save direction of the E round trip: the judge types a deduction, the
              // API only ever receives an execution score.
              const value =
                raw !== undefined && E_BOX_KEYS.includes(b.key)
                  ? deductionToScore(raw)
                  : raw;
              return [b.key, value];
            }),
          ),
          penalty: penaltyLocked ? undefined : (parseBox(values.penalty) ?? 0),
          currentPenalty: routine ? toNum(routine.penalty) : 0,
        });
        const clean =
          !result.formError && Object.keys(result.boxErrors).length === 0;
        // Re-baseline dirtiness to the just-saved values (not to empty): without
        // this, isDirty compares against mount-time defaults forever and the
        // discard guard would prompt even after a successful save.
        if (clean) reset(values);
        setJustSaved(clean);
        if (result.formError) {
          setError("root.server", { type: "server", message: result.formError });
        }
        for (const [key, message] of Object.entries(result.boxErrors)) {
          setError(key as BoxKey | "penalty", { type: "server", message });
        }
        onSaved(result, next && clean);
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
        aria-label={key === "penalty" ? "Penalty" : BOX_LABELS[key]}
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
        {boxes.map((box) =>
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
      {formState.errors.root?.server && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {formState.errors.root.server.message}
        </p>
      )}
      <div className="mt-4 flex gap-6 rounded border border-dashed border-gray-300 p-2 text-sm">
        {band === "1-3" && <span>Final: <strong>{fmt(preview.final)}</strong></span>}
        {band !== "1-3" && <span>D: <strong>{fmt(preview.d)}</strong></span>}
        {band === "8+" && <span>A: <strong>{fmt(preview.a)}</strong></span>}
        {band !== "1-3" && <span>E: <strong>{fmt(preview.e)}</strong></span>}
        {/* Only sign a penalty that exists -- "−0.00" reads as a negative zero. */}
        <span>
          Penalty: <strong>{preview.penalty === 0 ? fmt(0) : `−${fmt(preview.penalty)}`}</strong>
        </span>
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
          {justSaved && (
            <span className="text-sm font-semibold text-green-700">Saved ✓</span>
          )}
        </div>
      )}
    </form>
  );
}
