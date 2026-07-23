import {
  loadPanel,
  savePanel,
  PANEL_SLOTS,
  SLOTS_BY_BAND,
  REQUIRED_SLOTS,
  SLOT_CONFLICT_GROUPS,
} from "../../../src/features/scoring/panel-storage";

test("round-trips a panel assignment per meet", () => {
  savePanel(5, { D: 1, E1: 2, E2: 3, A1: 4 });
  expect(loadPanel(5)).toEqual({ D: 1, E1: 2, E2: 3, A1: 4 });
  expect(loadPanel(6)).toEqual({});
});

test("survives corrupt storage", () => {
  localStorage.setItem("rhythmiq.panel.7", "not json");
  expect(loadPanel(7)).toEqual({});
});

test("drops wrong-shaped storage instead of passing junk to boxesFor", () => {
  localStorage.setItem("rhythmiq.panel.8", "[]");
  expect(loadPanel(8)).toEqual({});
  // a non-numeric judge id would count as an "assigned" slot downstream
  localStorage.setItem("rhythmiq.panel.9", JSON.stringify({ D: "x", E1: 2 }));
  expect(loadPanel(9)).toEqual({ E1: 2 });
  // unknown keys are not panel slots
  localStorage.setItem("rhythmiq.panel.10", JSON.stringify({ X: 1 }));
  expect(loadPanel(10)).toEqual({});
});

it("orders slots F1-F4, D, DB1, DB2, A1, A2, E1-E4", () => {
  expect(PANEL_SLOTS).toEqual([
    "F1", "F2", "F3", "F4", "D", "DB1", "DB2", "A1", "A2", "E1", "E2", "E3", "E4",
  ]);
});

it("migrates a legacy A slot to A1", () => {
  // Panels saved before the 8+ band gained a second artistry judge used a single "A".
  localStorage.setItem("rhythmiq.panel.7", JSON.stringify({ D: 1, A: 2, E1: 3 }));

  expect(loadPanel(7)).toEqual({ D: 1, A1: 2, E1: 3 });
});

it("does not let a legacy A overwrite an explicit A1", () => {
  localStorage.setItem("rhythmiq.panel.7", JSON.stringify({ A: 2, A1: 9 }));

  expect(loadPanel(7)).toEqual({ A1: 9 });
});

it("migrates a legacy F slot to F1", () => {
  localStorage.setItem("rhythmiq.panel.8", JSON.stringify({ F: 9 }));
  expect(loadPanel(8)).toEqual({ F1: 9 });
});

it("does not let a legacy F overwrite an explicit F1", () => {
  localStorage.setItem("rhythmiq.panel.9", JSON.stringify({ F: 9, F1: 3 }));
  expect(loadPanel(9)).toEqual({ F1: 3 });
});

it("keeps the new slots", () => {
  localStorage.setItem(
    "rhythmiq.panel.7",
    JSON.stringify({ F: 1, DB1: 2, DB2: 3, A1: 4, A2: 5 }),
  );

  expect(loadPanel(7)).toEqual({ F1: 1, DB1: 2, DB2: 3, A1: 4, A2: 5 });
});

it("maps each band to the slots that band actually uses", () => {
  expect(SLOTS_BY_BAND["1-3"]).toEqual(["F1", "F2", "F3", "F4"]);
  expect(SLOTS_BY_BAND["4-7"]).toEqual(["DB1", "DB2", "E1", "E2"]);
  expect(SLOTS_BY_BAND["8+"]).toEqual(["D", "A1", "A2", "E1", "E2", "E3", "E4"]);
});

it("requires the minimum viable panel per band", () => {
  // F4/E3/E4 and A2 legitimately stay empty on a small panel, as before.
  expect(REQUIRED_SLOTS["1-3"]).toEqual(["F1", "F2", "F3"]);
  expect(REQUIRED_SLOTS["4-7"]).toEqual(["DB1", "DB2", "E1", "E2"]);
  expect(REQUIRED_SLOTS["8+"]).toEqual(["D", "A1", "E1", "E2"]);
});

it("groups F1-F4 as conflicting (all write the final panel)", () => {
  expect(SLOT_CONFLICT_GROUPS).toContainEqual(["F1", "F2", "F3", "F4"]);
});
