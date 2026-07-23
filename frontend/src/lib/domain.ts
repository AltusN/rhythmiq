import type { AgeGroup, Apparatus, JudgeCategory, Level, MeetStatus } from "../api/types";

export const APPARATUS: Apparatus[] = [
  "rope", "hoop", "ball", "clubs", "ribbon", "freehand",
];

// Age order, matching the AgeGroup enum's declaration order in app/models.py and the
// Postgres enum's sort order. These bands do not form one ladder: u7-o11 are the
// levels 1-3 bands, u12-o15 belong to the higher levels -- there is no single correct
// order, so this order is deliberate but arbitrary.
export const AGE_GROUPS: AgeGroup[] = [
  "u7", "u8", "u9", "u10", "u11", "o11", "u12", "u13", "u14", "u15", "o14", "o15",
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

/**
 * FIG judging categories, highest (1) to lowest (4) — General Judges' Rules 2025-2028
 * art. 2.6, mirrored by app.models.JudgeCategory. FIG writes these as arabic numerals
 * ("Category 1", "Cat. 4"), never roman, so the labels follow suit rather than going
 * through `labelize` (which would render "category 1", lowercase and unlabelled).
 *
 * A judge may legitimately have none: the scale only covers brevet holders, and the
 * rules rank "national level" below Category 3.
 */
export const JUDGE_CATEGORIES: { value: JudgeCategory; label: string }[] = [
  { value: "category_1", label: "Category 1" },
  { value: "category_2", label: "Category 2" },
  { value: "category_3", label: "Category 3" },
  { value: "category_4", label: "Category 4" },
];

export function judgeCategoryLabel(value: JudgeCategory | null | undefined): string {
  return JUDGE_CATEGORIES.find((c) => c.value === value)?.label ?? "—";
}

export function labelize(value: string): string {
  return value.replace(/_/g, " ");
}

/**
 * Badge colour per meet status. Colour reinforces the text label, never replaces it,
 * so nothing here is load-bearing for accessibility. `in_progress` gets the loudest
 * colour: on meet day the live meet is the one you need to find at a glance.
 */
const MEET_STATUS_BADGE_CLASSES: Record<MeetStatus, string> = {
  draft: "bg-gray-100 text-gray-700",
  scheduled: "bg-blue-100 text-blue-800",
  in_progress: "bg-green-100 text-green-800",
  completed: "bg-slate-200 text-slate-700",
  cancelled: "bg-red-100 text-red-800 line-through",
};

export function meetStatusBadgeClass(status: MeetStatus): string {
  return MEET_STATUS_BADGE_CLASSES[status];
}

export function isMeetLocked(status: MeetStatus): boolean {
  return status === "completed" || status === "cancelled";
}
