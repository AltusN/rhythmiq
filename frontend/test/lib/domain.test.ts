import { expect, test } from "vitest";
import type { MeetStatus } from "../../src/api/types";
import {
  isMeetLocked,
  labelize,
  meetStatusBadgeClass,
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

test("every meet status has a distinct badge colour", () => {
  // Meet.status gates real behaviour (deletes rejected once in_progress/completed,
  // standings go final on completed), so an operator has to be able to spot it.
  const statuses: MeetStatus[] = [
    "draft",
    "scheduled",
    "in_progress",
    "completed",
    "cancelled",
  ];
  const classes = statuses.map((s) => meetStatusBadgeClass(s));
  expect(classes.every((c) => c.length > 0)).toBe(true);
  expect(new Set(classes).size).toBe(statuses.length);
});

test("in_progress is the only green badge", () => {
  // The loudest colour goes to the one status that means "happening right now".
  expect(meetStatusBadgeClass("in_progress")).toContain("green");
  expect(meetStatusBadgeClass("draft")).not.toContain("green");
  expect(meetStatusBadgeClass("scheduled")).not.toContain("green");
  expect(meetStatusBadgeClass("completed")).not.toContain("green");
  expect(meetStatusBadgeClass("cancelled")).not.toContain("green");
});
