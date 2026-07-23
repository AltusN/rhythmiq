import {
  computeSaveOps,
  reconcileBoxesWithHistory,
  type BoxDef,
  type ExistingScore,
} from "../../../src/features/scoring/save-diff";

const boxes: BoxDef[] = [
  { key: "dBody1", panel: "difficulty_body", judgeId: 1 },
  { key: "dApp", panel: "difficulty_apparatus", judgeId: 1 },
  { key: "a1", panel: "artistry", judgeId: 4 },
  { key: "e1", panel: "execution", judgeId: 2 },
  { key: "e2", panel: "execution", judgeId: 3 },
  { key: "e3", panel: "execution", judgeId: undefined },
  { key: "e4", panel: "execution", judgeId: undefined },
];

test("new values on empty routine become creates", () => {
  const ops = computeSaveOps(boxes, [], { dBody1: 7.3, e1: 8.25 });
  expect(ops.creates).toEqual([
    { boxKey: "dBody1", judge_id: 1, panel: "difficulty_body", value: 7.3 },
    { boxKey: "e1", judge_id: 2, panel: "execution", value: 8.25 },
  ]);
  expect(ops.updates).toEqual([]);
  expect(ops.deletes).toEqual([]);
});

test("changed values update, cleared values delete, equal values are no-ops", () => {
  const existing: ExistingScore[] = [
    { id: 11, judge_id: 1, panel: "difficulty_body", value: 7.3 },
    { id: 12, judge_id: 2, panel: "execution", value: 8.0 },
    { id: 13, judge_id: 3, panel: "execution", value: 8.5 },
  ];
  const ops = computeSaveOps(boxes, existing, { dBody1: 7.3, e1: 8.1, e2: undefined });
  expect(ops.creates).toEqual([]);
  expect(ops.updates).toEqual([{ boxKey: "e1", id: 12, value: 8.1 }]);
  expect(ops.deletes).toEqual([{ boxKey: "e2", id: 13 }]);
});

test("boxes without an assigned judge are skipped entirely", () => {
  const ops = computeSaveOps(boxes, [], { e3: 9.0 });
  expect(ops).toEqual({ creates: [], updates: [], deletes: [] });
});

test("two D boxes for the same judge map to different panels", () => {
  const ops = computeSaveOps(boxes, [], { dBody1: 7.0, dApp: 6.5 });
  expect(ops.creates.map((c) => c.panel)).toEqual([
    "difficulty_body",
    "difficulty_apparatus",
  ]);
});

test("scores from judges outside the panel are never touched", () => {
  const stranger: ExistingScore[] = [
    { id: 99, judge_id: 42, panel: "execution", value: 6.0 },
  ];
  const ops = computeSaveOps(boxes, stranger, {});
  expect(ops).toEqual({ creates: [], updates: [], deletes: [] });
});

test("clearing a panel box deletes only that judge's row, never a stranger's", () => {
  const existing: ExistingScore[] = [
    { id: 99, judge_id: 42, panel: "execution", value: 6.0 },
    { id: 12, judge_id: 2, panel: "execution", value: 8.0 },
  ];
  const ops = computeSaveOps(boxes, existing, { e1: undefined });
  expect(ops.deletes).toEqual([{ boxKey: "e1", id: 12 }]);
});

describe("reconcileBoxesWithHistory — occupied boxes take the judge who gave the mark", () => {
  test("normal case: a mark for the current slot judge leaves the box untouched", () => {
    const marks: ExistingScore[] = [
      { id: 11, judge_id: 1, panel: "difficulty_body", value: 7.3 },
      { id: 12, judge_id: 2, panel: "execution", value: 8.0 },
    ];
    // Same judges as the boxes above -> nothing reassigned.
    expect(reconcileBoxesWithHistory(boxes, marks)).toEqual(boxes);
  });

  test("an orphan mark (judge not in any current slot) fills an empty box with its historical judge", () => {
    // The Final box's current slot is judge 3, but the routine's only final mark belongs
    // to judge 1 (seeded data, or an F slot reassigned after scoring). The box must adopt
    // judge 1 so the mark loads and later updates in place.
    const finalBoxes: BoxDef[] = [{ key: "final1", panel: "final", judgeId: 3 }];
    const marks: ExistingScore[] = [{ id: 155, judge_id: 1, panel: "final", value: 10.1 }];
    expect(reconcileBoxesWithHistory(finalBoxes, marks)).toEqual([
      { key: "final1", panel: "final", judgeId: 1 },
    ]);
  });

  test("current-slot marks stay put; leftover orphans fill the remaining boxes in id order", () => {
    // E1/E2 belong to current judges 2/3; the routine also has marks from off-panel
    // judges 7/8. Judges 2's mark keeps E1; judge 7/8's marks fill E-boxes with no
    // current-judge mark, historically.
    const eBoxes: BoxDef[] = [
      { key: "e1", panel: "execution", judgeId: 2 },
      { key: "e2", panel: "execution", judgeId: 3 },
      { key: "e3", panel: "execution", judgeId: 9 },
      { key: "e4", panel: "execution", judgeId: 10 },
    ];
    const marks: ExistingScore[] = [
      { id: 20, judge_id: 2, panel: "execution", value: 8.0 },
      { id: 21, judge_id: 7, panel: "execution", value: 8.5 },
      { id: 22, judge_id: 8, panel: "execution", value: 8.6 },
    ];
    expect(reconcileBoxesWithHistory(eBoxes, marks)).toEqual([
      { key: "e1", panel: "execution", judgeId: 2 }, // own mark, unchanged
      { key: "e2", panel: "execution", judgeId: 7 }, // empty -> first orphan (id 21)
      { key: "e3", panel: "execution", judgeId: 8 }, // empty -> next orphan (id 22)
      { key: "e4", panel: "execution", judgeId: 10 }, // no orphan left, stays for new entry
    ]);
  });

  test("editing an orphan-filled box updates its mark by id, never creating a duplicate", () => {
    // The end-to-end correctness guarantee: reconcile then computeSaveOps must UPDATE the
    // historical mark, not POST a second mark on the same panel (which would shift the
    // trimmed-mean total).
    const finalBoxes: BoxDef[] = [{ key: "final1", panel: "final", judgeId: 3 }];
    const marks: ExistingScore[] = [{ id: 155, judge_id: 1, panel: "final", value: 10.1 }];
    const reconciled = reconcileBoxesWithHistory(finalBoxes, marks);
    const ops = computeSaveOps(reconciled, marks, { final1: 11.0 });
    expect(ops.creates).toEqual([]);
    expect(ops.updates).toEqual([{ boxKey: "final1", id: 155, value: 11.0 }]);
    expect(ops.deletes).toEqual([]);
  });

  test("a fresh routine (no marks) leaves boxes on their current-panel judges for new entry", () => {
    expect(reconcileBoxesWithHistory(boxes, [])).toEqual(boxes);
  });
});
