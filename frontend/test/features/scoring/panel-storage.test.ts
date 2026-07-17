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
