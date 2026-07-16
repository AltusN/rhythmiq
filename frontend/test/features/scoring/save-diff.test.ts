import {
  computeSaveOps,
  type BoxDef,
  type ExistingScore,
} from "../../../src/features/scoring/save-diff";

const boxes: BoxDef[] = [
  { key: "dBody", panel: "difficulty_body", judgeId: 1 },
  { key: "dApp", panel: "difficulty_apparatus", judgeId: 1 },
  { key: "a", panel: "artistry", judgeId: 4 },
  { key: "e1", panel: "execution", judgeId: 2 },
  { key: "e2", panel: "execution", judgeId: 3 },
  { key: "e3", panel: "execution", judgeId: undefined },
  { key: "e4", panel: "execution", judgeId: undefined },
];

test("new values on empty routine become creates", () => {
  const ops = computeSaveOps(boxes, [], { dBody: 7.3, e1: 8.25 });
  expect(ops.creates).toEqual([
    { boxKey: "dBody", judge_id: 1, panel: "difficulty_body", value: 7.3 },
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
  const ops = computeSaveOps(boxes, existing, { dBody: 7.3, e1: 8.1, e2: undefined });
  expect(ops.creates).toEqual([]);
  expect(ops.updates).toEqual([{ boxKey: "e1", id: 12, value: 8.1 }]);
  expect(ops.deletes).toEqual([{ boxKey: "e2", id: 13 }]);
});

test("boxes without an assigned judge are skipped entirely", () => {
  const ops = computeSaveOps(boxes, [], { e3: 9.0 });
  expect(ops).toEqual({ creates: [], updates: [], deletes: [] });
});

test("two D boxes for the same judge map to different panels", () => {
  const ops = computeSaveOps(boxes, [], { dBody: 7.0, dApp: 6.5 });
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
  expect(ops.deletes).toEqual([]);
});
