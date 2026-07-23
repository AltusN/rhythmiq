/**
 * Mirrors backend/app/scoring.py — keep the worked examples in the tests in sync.
 *
 * The band table below is the frontend half of the spec's "one declarative scoring
 * profile" decision (docs/superpowers/specs/2026-07-20-level-banded-scoring-design.md).
 * Any change here needs the matching change in app/scoring.py, and vice versa.
 */

export const TRIM_THRESHOLD = 4;

/** Execution is a score out of 10 at EVERY level; the form is what speaks deductions. */
export const E_MAX = 10;

export type Band = "1-3" | "4-7" | "8+";
export type MedalMode = "cutoff" | "placement";

export interface ScoringProfile {
  band: Band;
  /** Panel values (matching the API's Panel enum) that are legal at this band. */
  panels: readonly string[];
  medalMode: MedalMode;
  tieBreakOnExecution: boolean;
}

const BAND_1_3: ScoringProfile = {
  band: "1-3",
  panels: ["final"],
  medalMode: "cutoff",
  tieBreakOnExecution: false,
};

const BAND_4_7: ScoringProfile = {
  band: "4-7",
  panels: ["difficulty_body", "execution"],
  medalMode: "placement",
  tieBreakOnExecution: false,
};

const BAND_8_PLUS: ScoringProfile = {
  band: "8+",
  panels: ["difficulty_body", "difficulty_apparatus", "artistry", "execution"],
  medalMode: "placement",
  tieBreakOnExecution: true,
};

const PROFILE_BY_LEVEL: Readonly<Record<string, ScoringProfile>> = {
  level_1: BAND_1_3,
  level_2: BAND_1_3,
  level_3: BAND_1_3,
  level_4: BAND_4_7,
  level_5: BAND_4_7,
  level_6: BAND_4_7,
  level_7: BAND_4_7,
};

/**
 * The scoring band governing `level`.
 *
 * Deliberately falls back to 8+ for an unknown level instead of throwing — unlike the
 * backend, which builds its map exhaustively over the Level enum and raises. The level
 * string arrives off the wire here, and a UI that crashes mid-meet on a level added
 * server-side is worse than one that shows the full panel.
 */
export function profileForLevel(level: string): ScoringProfile {
  return PROFILE_BY_LEVEL[level] ?? BAND_8_PLUS;
}

/** Guards against binary-float dust (10 - 0.05) reaching the 0.05-increment check. */
function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

/**
 * Save direction of the E round trip: a judge writes 1.5 meaning "1.5 off", and the
 * API stores the resulting execution score 8.5. See scoreToDeduction for the inverse —
 * both directions are required, or a judge reopening a routine sees 8.50 in the box
 * where they typed 1.50.
 *
 * Levels 1-3 are NOT deductions: that band's single mark is a straight score out of 13
 * and is neither converted nor inverted.
 */
export function deductionToScore(deduction: number): number {
  return round2(E_MAX - deduction);
}

/** Load direction of the E round trip. See deductionToScore. */
export function scoreToDeduction(score: number): number {
  return round2(E_MAX - score);
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

/**
 * Marks grouped by panel, exactly as compute_routine_score groups them — so that the
 * two-DB-judges case at levels 4-7 and the four-E-judges case at 8+ reduce through the
 * same code path on both sides. `eScores` are execution SCORES here, already converted
 * from the form's deductions by the caller — computePreview does no conversion itself.
 */
export interface PreviewInput {
  band: Band;
  dBodyScores?: number[];
  dAppScores?: number[];
  artistryScores?: number[];
  eScores?: number[];
  finalScores?: number[];
  penalty?: number;
}

export interface ScorePreview {
  d: number;
  a: number;
  e: number;
  final: number;
  penalty: number;
  total: number;
}

/**
 * Client-side preview only — server standings are the source of truth. The server
 * computes with Decimal; this uses binary floats, so the displayed total can drift
 * from the server's by ±0.01 in rare rounding cases. Never persist these numbers.
 */
export function computePreview(input: PreviewInput): ScorePreview {
  const penalty = input.penalty ?? 0;

  if (input.band === "1-3") {
    // A panel of up to four marks (each out of 13), combined by the SAME trimmedMean the
    // other bands use: one mark returns itself, three plain-average, four trim to the
    // middle two. The result IS the routine's score, less penalty.
    const final = trimmedMean(input.finalScores ?? []);
    return { d: 0, a: 0, e: 0, final, penalty, total: final - penalty };
  }

  // At 4-7 there is no DA, so trimmedMean([]) is 0 and (DB + DA) reduces to the
  // required average of the two DB marks — adding zero is a no-op, same as the backend.
  const d = trimmedMean(input.dBodyScores ?? []) + trimmedMean(input.dAppScores ?? []);
  const a = trimmedMean(input.artistryScores ?? []);
  const e = trimmedMean(input.eScores ?? []);
  return { d, a, e, final: 0, penalty, total: d + a + e - penalty };
}
