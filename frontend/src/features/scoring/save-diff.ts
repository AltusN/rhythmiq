import type { Panel } from "../../api/types";

export type BoxKey =
  | "final1"
  | "final2"
  | "final3"
  | "final4"
  | "dBody1"
  | "dBody2"
  | "dApp"
  | "a1"
  | "a2"
  | "e1"
  | "e2"
  | "e3"
  | "e4";

export interface BoxDef {
  key: BoxKey;
  panel: Panel;
  judgeId: number | undefined;
}

export interface ExistingScore {
  id: number;
  judge_id: number;
  panel: Panel;
  value: number;
}

/**
 * The stored score a box binds to, keyed on (judge, panel) -- unique per routine
 * (uq_judge_score_routine_judge_panel). Load (ScoreForm.defaultValues) and save
 * (computeSaveOps) MUST route through this one function so they can never disagree about
 * which row a box owns -- a divergence would silently create a duplicate mark. Callers
 * pass boxes already reconciled with history (see reconcileBoxesWithHistory), so an
 * occupied box's judgeId is the judge who actually gave the mark, not the current seat.
 */
export function findBoxScore<T extends { judge_id: number; panel: Panel }>(
  box: BoxDef,
  existing: readonly T[],
): T | undefined {
  return existing.find((s) => s.judge_id === box.judgeId && s.panel === box.panel);
}

/**
 * Rebind boxes to the judges who ACTUALLY gave the routine's marks, so a scored routine
 * displays its historical record rather than the current (mutable, per-browser) panel
 * seating. A JudgeScore is a historical fact -- once entered, the panel shouldn't change
 * (Altus, 2026-07-21) -- but the localStorage panel can, and seeded/imported data may
 * attribute marks to judges who aren't in the current slots. Without this, such a mark
 * doesn't load (its box shows empty) and a save POSTs a SECOND mark on the same panel,
 * shifting the trimmed-mean total.
 *
 * Per panel, in two passes:
 *   1. A box whose CURRENT judge already has a mark keeps that judge (normal case is a
 *      no-op -- boxes are returned unchanged when the panel never moved).
 *   2. Marks left over ("orphans" -- their judge is in no current slot) fill the still-
 *      empty boxes, in mark-id order, each box adopting its orphan's historical judge.
 * Boxes with no mark to adopt keep their current-panel judge, so new marks still
 * attribute to whoever the scorer has seated. Returns fresh box objects; never mutates
 * the input.
 */
export function reconcileBoxesWithHistory<
  T extends { id: number; judge_id: number; panel: Panel },
>(boxes: BoxDef[], existing: readonly T[]): BoxDef[] {
  const result = boxes.map((box) => ({ ...box }));
  const panels = new Set(result.map((box) => box.panel));
  for (const panel of panels) {
    const panelBoxes = result.filter((box) => box.panel === panel);
    const marks = existing
      .filter((s) => s.panel === panel)
      .slice()
      .sort((a, b) => a.id - b.id);
    const filled = new Set<BoxDef>();
    const usedMarkIds = new Set<number>();
    // Pass 1: boxes whose current judge already holds a mark stay as-is.
    for (const box of panelBoxes) {
      if (box.judgeId === undefined) continue;
      const own = marks.find((m) => m.judge_id === box.judgeId && !usedMarkIds.has(m.id));
      if (own) {
        usedMarkIds.add(own.id);
        filled.add(box);
      }
    }
    // Pass 2: orphan marks fill the remaining boxes, historically.
    const orphans = marks.filter((m) => !usedMarkIds.has(m.id));
    let next = 0;
    for (const box of panelBoxes) {
      if (next >= orphans.length) break;
      if (filled.has(box)) continue;
      box.judgeId = orphans[next].judge_id;
      next += 1;
    }
  }
  return result;
}

export interface CreateOp { boxKey: BoxKey; judge_id: number; panel: Panel; value: number }
export interface UpdateOp { boxKey: BoxKey; id: number; value: number }
export interface DeleteOp { boxKey: BoxKey; id: number }

export interface SaveOps {
  creates: CreateOp[];
  updates: UpdateOp[];
  deletes: DeleteOp[];
}

/**
 * Each box maps to at most one JudgeScore row via (judge, panel) — unique per routine
 * (uq_judge_score_routine_judge_panel). Boxes with no judge assigned are skipped;
 * existing scores from judges outside the panel are left alone.
 */
export function computeSaveOps(
  boxes: BoxDef[],
  existing: ExistingScore[],
  values: Partial<Record<BoxKey, number | undefined>>,
): SaveOps {
  const ops: SaveOps = { creates: [], updates: [], deletes: [] };
  for (const box of boxes) {
    if (box.judgeId === undefined) continue;
    const current = findBoxScore(box, existing);
    const value = values[box.key];
    if (value === undefined) {
      if (current) ops.deletes.push({ boxKey: box.key, id: current.id });
    } else if (!current) {
      ops.creates.push({
        boxKey: box.key,
        judge_id: box.judgeId,
        panel: box.panel,
        value,
      });
    } else if (Math.abs(current.value - value) > 1e-9) {
      ops.updates.push({ boxKey: box.key, id: current.id, value });
    }
  }
  return ops;
}
