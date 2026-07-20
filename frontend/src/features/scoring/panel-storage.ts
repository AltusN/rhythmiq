import type { Band } from "../../lib/score-math";

/**
 * Judge slots across all three scoring bands. "D" is the 8+ difficulty judge and covers
 * both D-Body and D-App (one judge, two marks, two panels — legal because JudgeScore is
 * unique on (routine, judge, panel)). Levels 4-7 instead have TWO body judges, DB1/DB2,
 * and no apparatus difficulty at all — the asymmetry is deliberate, see the spec.
 *
 * "A" is a DEPRECATED legacy slot: the 8+ band now has two artistry judges, A1/A2. It is
 * kept in the union (but out of PANEL_SLOTS and every band's slot list) purely so
 * ScoreForm.tsx (`panel.A`, its last remaining consumer) keeps compiling until Task 7
 * migrates its boxes to A1/A2; Task 8 then deletes this member. ScoringPage was already
 * migrated off "A". loadPanel migrates a stored legacy "A" to "A1".
 */
export type PanelSlot =
  | "F"
  | "D"
  | "DB1"
  | "DB2"
  | "A"
  | "A1"
  | "A2"
  | "E1"
  | "E2"
  | "E3"
  | "E4";

export const PANEL_SLOTS: PanelSlot[] = [
  "F",
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
  "1-3": ["F"],
  "4-7": ["DB1", "DB2", "E1", "E2"],
  "8+": ["D", "A1", "A2", "E1", "E2", "E3", "E4"],
};

/** The minimum viable panel per band; E3/E4 and A2 legitimately stay empty. */
export const REQUIRED_SLOTS: Record<Band, PanelSlot[]> = {
  "1-3": ["F"],
  "4-7": ["DB1", "DB2", "E1", "E2"],
  "8+": ["D", "A1", "E1", "E2"],
};

/**
 * Slots that write to the same API panel, and therefore may not share a judge — a
 * second mark from the same judge on the same panel violates
 * uq_judge_score_routine_judge_panel and the save would fail at the API.
 */
export const SLOT_CONFLICT_GROUPS: PanelSlot[][] = [
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
    return panel;
  } catch {
    return {};
  }
}

export function savePanel(meetId: number, panel: PanelAssignment): void {
  localStorage.setItem(key(meetId), JSON.stringify(panel));
}
