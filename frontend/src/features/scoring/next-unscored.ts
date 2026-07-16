import type { MeetEntryRead } from "../../api/types";

/** Next entry without a scored total, scanning forward from current and wrapping. */
export function nextUnscored(
  entries: MeetEntryRead[],
  scoredTotals: ReadonlyMap<number, string>,
  currentId: number | null,
): MeetEntryRead | null {
  if (entries.length === 0) return null;
  const start = currentId === null ? -1 : entries.findIndex((e) => e.id === currentId);
  for (let offset = 1; offset <= entries.length; offset++) {
    const candidate = entries[(start + offset) % entries.length];
    if (candidate.id === currentId) continue;
    if (!scoredTotals.has(candidate.id)) return candidate;
  }
  return null;
}
