import { matchesSearch } from "../../../../src/features/admin/hooks/useResourceList";

test("matchesSearch is case-insensitive and trims the query", () => {
  expect(matchesSearch("Anna Botha", "botha")).toBe(true);
  expect(matchesSearch("Anna Botha", "  ANNA ")).toBe(true);
  expect(matchesSearch("Anna Botha", "nel")).toBe(false);
});

test("an empty query matches everything", () => {
  expect(matchesSearch("Anna Botha", "")).toBe(true);
  expect(matchesSearch("Anna Botha", "   ")).toBe(true);
});
