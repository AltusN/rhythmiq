import type { Panel } from "../../api/types";

export type BoxKey = "dBody" | "dApp" | "a" | "e1" | "e2" | "e3" | "e4";

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
    const current = existing.find(
      (s) => s.judge_id === box.judgeId && s.panel === box.panel,
    );
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
