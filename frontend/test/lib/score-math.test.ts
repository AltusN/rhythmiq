import { expect, test } from "vitest";
import { computePreview, isEOnlyLevel, trimmedMean } from "../../src/lib/score-math";

test("trimmedMean averages plainly below 4 scores", () => {
  expect(trimmedMean([])).toBe(0);
  expect(trimmedMean([8.25])).toBeCloseTo(8.25);
  expect(trimmedMean([8.25, 8.4, 8.1])).toBeCloseTo(8.25);
});

test("trimmedMean drops high and low at 4+ scores", () => {
  expect(trimmedMean([8.0, 8.1, 8.2, 9.0])).toBeCloseTo(8.15);
  expect(trimmedMean([5.0, 8.0, 8.5, 9.0, 10.0])).toBeCloseTo(8.5);
});

test("levels 1-7 are E-only, level_8+ are not", () => {
  expect(isEOnlyLevel("level_1")).toBe(true);
  expect(isEOnlyLevel("level_7")).toBe(true);
  expect(isEOnlyLevel("level_8")).toBe(false);
  expect(isEOnlyLevel("senior")).toBe(false);
});

test("computePreview matches the v3 mockup worked example", () => {
  const p = computePreview({
    dBody: 7.3,
    dApp: 6.9,
    artistry: 8.9,
    eScores: [8.25, 8.4, 8.1],
    penalty: 0.1,
  });
  expect(p.d).toBeCloseTo(14.2);
  expect(p.a).toBeCloseTo(8.9);
  expect(p.e).toBeCloseTo(8.25);
  expect(p.total).toBeCloseTo(31.25);
});

test("computePreview treats missing panels as 0", () => {
  const p = computePreview({ eScores: [8.0, 7.9] });
  expect(p.d).toBe(0);
  expect(p.a).toBe(0);
  expect(p.e).toBeCloseTo(7.95);
  expect(p.total).toBeCloseTo(7.95);
});
