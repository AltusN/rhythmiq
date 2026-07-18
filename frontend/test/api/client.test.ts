import { apiDetail, toDec, toNum } from "../../src/api/client";

test("toNum parses Decimal strings and passes numbers through", () => {
  expect(toNum("7.30")).toBe(7.3);
  expect(toNum(8)).toBe(8);
  expect(toNum(null)).toBe(0);
  expect(toNum(undefined)).toBe(0);
  expect(toNum("")).toBe(0);
});

test("toDec formats to 2 decimals", () => {
  expect(toDec(7.3)).toBe("7.30");
  expect(toDec(0)).toBe("0.00");
});

test("apiDetail extracts string detail", () => {
  expect(apiDetail({ detail: "Meet with id 9 not found" })).toBe(
    "Meet with id 9 not found",
  );
  expect(apiDetail(undefined)).toBe("Request failed");
});

test("apiDetail formats 422 validation arrays as field: message lines", () => {
  const body = {
    detail: [
      { loc: ["body", "abbreviation"], msg: "String should have at most 10 characters" },
      { loc: ["body", "name"], msg: "Field required" },
    ],
  };
  expect(apiDetail(body)).toBe(
    "abbreviation: String should have at most 10 characters\nname: Field required",
  );
});

test("apiDetail falls back to JSON for unrecognised array shapes", () => {
  expect(apiDetail({ detail: [{ oops: 1 }] })).toBe('[{"oops":1}]');
});
