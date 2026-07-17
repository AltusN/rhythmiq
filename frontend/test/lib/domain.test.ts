import { expect, test } from "vitest";
import {
  isMeetLocked,
  labelize,
  MEET_STATUS_TRANSITIONS,
} from "../../src/lib/domain";

test("forward-only transitions mirror routers/meet.py", () => {
  expect(MEET_STATUS_TRANSITIONS.draft).toEqual(["scheduled", "cancelled"]);
  expect(MEET_STATUS_TRANSITIONS.scheduled).toEqual(["in_progress", "cancelled"]);
  expect(MEET_STATUS_TRANSITIONS.in_progress).toEqual(["completed", "cancelled"]);
  expect(MEET_STATUS_TRANSITIONS.completed).toEqual([]);
  expect(MEET_STATUS_TRANSITIONS.cancelled).toEqual([]);
});

test("meets lock when completed or cancelled", () => {
  expect(isMeetLocked("completed")).toBe(true);
  expect(isMeetLocked("cancelled")).toBe(true);
  expect(isMeetLocked("in_progress")).toBe(false);
});

test("labelize replaces underscores", () => {
  expect(labelize("in_progress")).toBe("in progress");
});
