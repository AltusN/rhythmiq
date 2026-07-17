import { apiDetail, client, toDec } from "../../api/client";
import type { components } from "../../api/schema";
import type { Apparatus } from "../../api/types";
import {
  computeSaveOps,
  type BoxDef,
  type BoxKey,
  type ExistingScore,
} from "./save-diff";

export interface SaveScoresArgs {
  routineId: number | undefined;
  entryId: number;
  apparatus: Apparatus;
  boxes: BoxDef[];
  existing: ExistingScore[];
  values: Partial<Record<BoxKey, number | undefined>>;
  penalty: number | undefined; // undefined = leave the routine's penalty unchanged
  currentPenalty: number;
}

export interface SaveScoresResult {
  routineId: number | null;
  boxErrors: Partial<Record<BoxKey | "penalty", string>>;
  formError?: string; // lazy routine creation failed; nothing was written
}

/**
 * Not atomic on purpose (see spec): each changed box is its own API call; a failing
 * box reports inline while the rest stand, so the scorekeeper fixes one box and
 * re-saves without re-entering everything.
 */
export async function saveScores(args: SaveScoresArgs): Promise<SaveScoresResult> {
  const boxErrors: SaveScoresResult["boxErrors"] = {};
  let routineId = args.routineId;

  if (routineId === undefined) {
    // RoutineCreate.penalty is required by the generated type (openapi-typescript doesn't
    // treat the backend's `Field(Decimal("0"), ...)` default as optional), but the server
    // already defaults it to 0 -- omit it on the wire (the lazy-create request is just
    // { entry_id, apparatus }) and assert the narrower literal against the generated type.
    const { data, error } = await client.POST("/routines/", {
      body: { entry_id: args.entryId, apparatus: args.apparatus } as components["schemas"]["RoutineCreate"],
    });
    if (error || !data) {
      return { routineId: null, boxErrors: {}, formError: apiDetail(error) };
    }
    routineId = data.id;
  }

  const ops = computeSaveOps(args.boxes, args.existing, args.values);

  for (const op of ops.creates) {
    const { error } = await client.POST("/judge-scores/", {
      body: {
        routine_id: routineId,
        judge_id: op.judge_id,
        panel: op.panel,
        value: toDec(op.value),
      },
    });
    if (error) boxErrors[op.boxKey] = apiDetail(error);
  }
  for (const op of ops.updates) {
    const { error } = await client.PATCH("/judge-scores/{judge_score_id}", {
      params: { path: { judge_score_id: op.id } },
      body: { value: toDec(op.value) },
    });
    if (error) boxErrors[op.boxKey] = apiDetail(error);
  }
  for (const op of ops.deletes) {
    const { error } = await client.DELETE("/judge-scores/{judge_score_id}", {
      params: { path: { judge_score_id: op.id } },
    });
    if (error) boxErrors[op.boxKey] = apiDetail(error);
  }

  if (
    args.penalty !== undefined &&
    Math.abs(args.penalty - args.currentPenalty) > 1e-9
  ) {
    const { error } = await client.PATCH("/routines/{routine_id}", {
      params: { path: { routine_id: routineId } },
      body: { penalty: toDec(args.penalty) },
    });
    if (error) boxErrors.penalty = apiDetail(error);
  }

  return { routineId, boxErrors };
}
