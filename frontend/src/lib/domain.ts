import type { AgeGroup, Apparatus, Level, MeetStatus } from "../api/types";

export const APPARATUS: Apparatus[] = [
  "rope", "hoop", "ball", "clubs", "ribbon", "freehand",
];

// Age order, matching the AgeGroup enum's declaration order in app/models.py and the
// Postgres enum's sort order. Two bandings coexist: u7-o11 alongside the older
// u12/u14/o14, which stay selectable because they are in live data.
export const AGE_GROUPS: AgeGroup[] = [
  "u7", "u8", "u9", "u10", "u11", "o11", "u12", "u14", "o14",
];

export const LEVELS: Level[] = [
  "level_1", "level_2", "level_3", "level_4", "level_5", "level_6", "level_7",
  "level_8", "level_9", "level_10",
  "high_performance_1", "high_performance_2", "high_performance_3", "high_performance_4",
  "pre_junior", "junior", "senior", "olympic",
];

/** Mirrors ALLOWED_STATUS_TRANSITIONS in backend/app/routers/meet.py. */
export const MEET_STATUS_TRANSITIONS: Record<MeetStatus, MeetStatus[]> = {
  draft: ["scheduled", "cancelled"],
  scheduled: ["in_progress", "cancelled"],
  in_progress: ["completed", "cancelled"],
  completed: [],
  cancelled: [],
};

/** Button label when transitioning TO this status. */
export const STATUS_ACTION_LABELS: Record<MeetStatus, string> = {
  draft: "Draft",
  scheduled: "Schedule",
  in_progress: "Start meet",
  completed: "Complete meet",
  cancelled: "Cancel meet",
};

export function labelize(value: string): string {
  return value.replace(/_/g, " ");
}

export function isMeetLocked(status: MeetStatus): boolean {
  return status === "completed" || status === "cancelled";
}
