/** Mirrors backend/app/scoring.py — keep the worked examples in the tests in sync. */

export const TRIM_THRESHOLD = 4;

const E_ONLY_LEVELS: ReadonlySet<string> = new Set([
  "level_1", "level_2", "level_3", "level_4", "level_5", "level_6", "level_7",
]);

/** Levels 1-7 are judged on Execution only (no D or A panels). */
export function isEOnlyLevel(level: string): boolean {
  return E_ONLY_LEVELS.has(level);
}

/** Below TRIM_THRESHOLD scores: plain average. At/above: drop high+low, average rest. */
export function trimmedMean(scores: number[]): number {
  if (scores.length === 0) return 0;
  if (scores.length < TRIM_THRESHOLD) {
    return scores.reduce((a, b) => a + b, 0) / scores.length;
  }
  const trimmed = [...scores].sort((a, b) => a - b).slice(1, -1);
  return trimmed.reduce((a, b) => a + b, 0) / trimmed.length;
}

export interface PreviewInput {
  dBody?: number;
  dApp?: number;
  artistry?: number;
  eScores: number[];
  penalty?: number;
}

export interface ScorePreview {
  d: number;
  a: number;
  e: number;
  penalty: number;
  total: number;
}

/** Client-side preview only — server standings are the source of truth. */
export function computePreview(input: PreviewInput): ScorePreview {
  const d = (input.dBody ?? 0) + (input.dApp ?? 0);
  const a = input.artistry ?? 0;
  const e = trimmedMean(input.eScores);
  const penalty = input.penalty ?? 0;
  return { d, a, e, penalty, total: d + a + e - penalty };
}
