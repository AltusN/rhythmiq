import { describe, expect, it, test } from "vitest";
import {
  computePreview,
  deductionToScore,
  profileForLevel,
  scoreToDeduction,
  trimmedMean,
} from "../../src/lib/score-math";

describe("trimmedMean", () => {
  it("plain-averages below the trim threshold", () => {
    expect(trimmedMean([8.8, 9.5, 7.2])).toBeCloseTo(8.5, 10);
    expect(trimmedMean([7.9, 8.3])).toBeCloseTo(8.1, 10);
    expect(trimmedMean([])).toBe(0);
  });

  it("drops the highest and lowest at or above the threshold", () => {
    expect(trimmedMean([8.5, 8.6, 8.7, 9.9])).toBeCloseTo(8.65, 10);
  });
});

describe("profileForLevel", () => {
  it("bands levels 1-3 as pre-aggregated with cutoff medals", () => {
    const profile = profileForLevel("level_2");
    expect(profile.band).toBe("1-3");
    expect(profile.panels).toEqual(["final"]);
    expect(profile.medalMode).toBe("cutoff");
    expect(profile.tieBreakOnExecution).toBe(false);
  });

  it("bands levels 4-7 as DB + E with placement medals", () => {
    const profile = profileForLevel("level_6");
    expect(profile.band).toBe("4-7");
    expect(profile.panels).toEqual(["difficulty_body", "execution"]);
    expect(profile.medalMode).toBe("placement");
    expect(profile.tieBreakOnExecution).toBe(false);
  });

  it("bands level 8 and above as the full FIG panel", () => {
    for (const level of ["level_8", "high_performance_1", "senior", "olympic"]) {
      expect(profileForLevel(level).band).toBe("8+");
    }
    expect(profileForLevel("senior").tieBreakOnExecution).toBe(true);
  });

  it("falls back to 8+ for an unrecognised level rather than throwing", () => {
    // The level string comes off the wire; the UI must not crash on a level the
    // frontend has not been rebuilt for. The backend deliberately does the opposite
    // and raises, because there the enum is exhaustive.
    expect(profileForLevel("level_99").band).toBe("8+");
  });
});

describe("E deduction round trip", () => {
  it("converts a deduction to a stored execution score", () => {
    expect(deductionToScore(1.5)).toBe(8.5);
    expect(deductionToScore(0)).toBe(10);
    expect(deductionToScore(10)).toBe(0);
  });

  it("converts a stored execution score back to a deduction", () => {
    expect(scoreToDeduction(8.5)).toBe(1.5);
    expect(scoreToDeduction(10)).toBe(0);
  });

  it("round-trips on 0.05 increments without drift", () => {
    for (let step = 0; step <= 200; step += 1) {
      const deduction = step * 0.05;
      expect(scoreToDeduction(deductionToScore(deduction))).toBeCloseTo(deduction, 10);
    }
  });
});

describe("band boundary at level_7/level_8", () => {
  test("levels 1-7 fall below the 8+ band, level_8 and up are 8+", () => {
    expect(profileForLevel("level_1").band).not.toBe("8+");
    expect(profileForLevel("level_7").band).not.toBe("8+");
    expect(profileForLevel("level_8").band).toBe("8+");
    expect(profileForLevel("senior").band).toBe("8+");
  });
});

describe("computePreview", () => {
  it("records the trimmed final mark at levels 1-3", () => {
    // One mark returns itself.
    expect(computePreview({ band: "1-3", finalScores: [11.75] })).toEqual({
      d: 0,
      a: 0,
      e: 0,
      final: 11.75,
      penalty: 0,
      total: 11.75,
    });
  });

  it("trims four final marks to the middle two at levels 1-3", () => {
    // [10, 11, 12, 13] -> drop 10 and 13 -> mean(11, 12) = 11.5
    expect(computePreview({ band: "1-3", finalScores: [10, 11, 12, 13] }).final).toBeCloseTo(
      11.5,
    );
  });

  it("plain-averages three final marks at levels 1-3", () => {
    // [10, 11, 12] -> 11 (below TRIM_THRESHOLD, no trim)
    expect(computePreview({ band: "1-3", finalScores: [10, 11, 12] }).final).toBeCloseTo(11);
  });

  it("subtracts penalty from the final mark at levels 1-3", () => {
    expect(
      computePreview({ band: "1-3", finalScores: [12], penalty: 0.3 }).total,
    ).toBeCloseTo(11.7);
  });

  it("averages the two DB marks at levels 4-7", () => {
    const preview = computePreview({
      band: "4-7",
      dBodyScores: [2.4, 2.6],
      eScores: [8.5, 8.7],
    });
    expect(preview.d).toBeCloseTo(2.5, 10);
    expect(preview.e).toBeCloseTo(8.6, 10);
    expect(preview.final).toBe(0);
    expect(preview.total).toBeCloseTo(11.1, 10);
  });

  it("sums DB and DA and trims E at 8+", () => {
    const preview = computePreview({
      band: "8+",
      dBodyScores: [5],
      dAppScores: [3],
      artistryScores: [8, 8.5],
      eScores: [8.5, 8.6, 8.7, 9.9],
    });
    expect(preview.d).toBeCloseTo(8, 10);
    expect(preview.a).toBeCloseTo(8.25, 10);
    expect(preview.e).toBeCloseTo(8.65, 10);
    expect(preview.total).toBeCloseTo(24.9, 10);
  });
});
