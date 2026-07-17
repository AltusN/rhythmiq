export type PanelSlot = "D" | "E1" | "E2" | "E3" | "E4" | "A";

export const PANEL_SLOTS: PanelSlot[] = ["D", "E1", "E2", "E3", "E4", "A"];

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
    const panel: PanelAssignment = {};
    for (const slot of PANEL_SLOTS) {
      const judgeId = (parsed as Record<string, unknown>)[slot];
      if (typeof judgeId === "number") panel[slot] = judgeId;
    }
    return panel;
  } catch {
    return {};
  }
}

export function savePanel(meetId: number, panel: PanelAssignment): void {
  localStorage.setItem(key(meetId), JSON.stringify(panel));
}
