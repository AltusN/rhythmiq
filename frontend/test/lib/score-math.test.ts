import { describe, expect, it } from "vitest";
import {
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
