import type { Band } from "../../lib/score-math";

/**
 * Judge slots across all three scoring bands. "D" is the 8+ difficulty judge and covers
 * both D-Body and D-App (one judge, two marks, two panels — legal because JudgeScore is
 * unique on (routine, judge, panel)). Levels 4-7 instead have TWO body judges, DB1/DB2,
 * and no apparatus difficulty at all — the asymmetry is deliberate, see the spec.
 *
 * loadPanel migrates a stored legacy "A" (the 8+ band's old single artistry slot) to
 * "A1", and a legacy "F" (the levels 1-3 band's old single final slot) to "F1".
 */
export type PanelSlot =
  | "F1"
  | "F2"
  | "F3"
  | "F4"
  | "D"
  | "DB1"
  | "DB2"
  | "A1"
  | "A2"
  | "E1"
  | "E2"
  | "E3"
  | "E4";

export const PANEL_SLOTS: PanelSlot[] = [
  "F1",
  "F2",
  "F3",
  "F4",
  "D",
  "DB1",
  "DB2",
  "A1",
  "A2",
  "E1",
  "E2",
  "E3",
  "E4",
];

/** Which slots each band actually uses — drives the setup dialog's grouping. */
export const SLOTS_BY_BAND: Record<Band, PanelSlot[]> = {
  "1-3": ["F1", "F2", "F3", "F4"],
  "4-7": ["DB1", "DB2", "E1", "E2"],
  "8+": ["D", "A1", "A2", "E1", "E2", "E3", "E4"],
};

/** The minimum viable panel per band; F4/E3/E4 and A2 legitimately stay empty. */
export const REQUIRED_SLOTS: Record<Band, PanelSlot[]> = {
  "1-3": ["F1", "F2", "F3"],
  "4-7": ["DB1", "DB2", "E1", "E2"],
  "8+": ["D", "A1", "E1", "E2"],
};

/**
 * Slots that write to the same API panel, and therefore may not share a judge — a
 * second mark from the same judge on the same panel violates
 * uq_judge_score_routine_judge_panel and the save would fail at the API.
 */
export const SLOT_CONFLICT_GROUPS: PanelSlot[][] = [
  ["F1", "F2", "F3", "F4"],
  ["DB1", "DB2"],
  ["A1", "A2"],
  ["E1", "E2", "E3", "E4"],
];

/** Slot -> judge id. Missing slot = no judge assigned (its boxes render disabled). */
export type PanelAssignment = Partial<Record<PanelSlot, number>>;

const key = (meetId: number) => `rhythmiq.panel.${meetId}`;

export function loadPanel(meetId: number): PanelAssignment {
  try {
    const raw = localStorage.getItem(key(meetId));
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return {};
    // Keep only known slots with numeric judge ids: a junk value like "x" would read
    // as an assigned judge downstream (boxesFor only checks !== undefined).
    const stored = parsed as Record<string, unknown>;
    const panel: PanelAssignment = {};
    for (const slot of PANEL_SLOTS) {
      const judgeId = stored[slot];
      if (typeof judgeId === "number") panel[slot] = judgeId;
    }
    // Panels saved before 8+ gained a second artistry judge used a single "A" slot.
    // Read it as A1 rather than dropping it, so a meet in progress keeps its panel.
    // An explicit A1 wins — it is the newer of the two.
    if (panel.A1 === undefined && typeof stored.A === "number") {
      panel.A1 = stored.A;
    }
    // Panels saved before levels 1-3 became a four-judge panel used a single "F" slot.
    // Read it as F1 rather than dropping it, so a meet in progress keeps its panel.
    // An explicit F1 wins — it is the newer of the two. Mirrors the "A" → "A1" case.
    if (panel.F1 === undefined && typeof stored.F === "number") {
      panel.F1 = stored.F;
    }
    return panel;
  } catch {
    return {};
  }
}

export function savePanel(meetId: number, panel: PanelAssignment): void {
  localStorage.setItem(key(meetId), JSON.stringify(panel));
}
