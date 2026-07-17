import { loadPanel, savePanel } from "../../../src/features/scoring/panel-storage";

test("round-trips a panel assignment per meet", () => {
  savePanel(5, { D: 1, E1: 2, E2: 3, A: 4 });
  expect(loadPanel(5)).toEqual({ D: 1, E1: 2, E2: 3, A: 4 });
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
