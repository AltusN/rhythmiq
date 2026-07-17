import { describe, test, expect } from "vitest";
import { nextUnscored } from "../../../src/features/scoring/next-unscored";
import { makeEntry } from "../../fixtures";

const e1 = makeEntry({ id: 1, bib_number: "11" });
const e2 = makeEntry({ id: 2, bib_number: "12" });
const e3 = makeEntry({ id: 3, bib_number: "13" });
const entries = [e1, e2, e3];

describe("nextUnscored", () => {
  test("advances to the next unscored entry after the current one", () => {
    const scored = new Map([[1, "24.85"]]);
    expect(nextUnscored(entries, scored, 2)?.id).toBe(3);
  });

  test("wraps around past the end", () => {
    const scored = new Map([[2, "20.00"], [3, "21.00"]]);
    expect(nextUnscored(entries, scored, 3)?.id).toBe(1);
  });

  test("returns null when everyone is scored", () => {
    const scored = new Map([[1, "1"], [2, "2"], [3, "3"]]);
    expect(nextUnscored(entries, scored, 1)).toBeNull();
  });

  test("with no current selection starts from the top", () => {
    expect(nextUnscored(entries, new Map(), null)?.id).toBe(1);
  });
});
