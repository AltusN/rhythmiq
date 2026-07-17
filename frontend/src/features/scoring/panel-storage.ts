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
    return parsed as PanelAssignment;
  } catch {
    return {};
  }
}

export function savePanel(meetId: number, panel: PanelAssignment): void {
  localStorage.setItem(key(meetId), JSON.stringify(panel));
}
