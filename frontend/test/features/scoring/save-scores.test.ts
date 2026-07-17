import { http, HttpResponse } from "msw";
import { saveScores } from "../../../src/features/scoring/save-scores";
import type { BoxDef } from "../../../src/features/scoring/save-diff";
import { makeRoutine } from "../../fixtures";
import { api, server } from "../../msw/server";

const boxes: BoxDef[] = [
  { key: "dBody", panel: "difficulty_body", judgeId: 1 },
  { key: "e1", panel: "execution", judgeId: 2 },
];

test("creates the routine lazily, posts scores as Decimal strings, patches penalty", async () => {
  const posted: Record<string, unknown>[] = [];
  let patchedPenalty: unknown = null;
  server.use(
    http.post(api("/routines/"), () =>
      HttpResponse.json(makeRoutine({ id: 77 }), { status: 201 }),
    ),
    http.post(api("/judge-scores/"), async ({ request }) => {
      posted.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({}, { status: 201 });
    }),
    http.patch(api("/routines/:routineId"), async ({ request }) => {
      patchedPenalty = await request.json();
      return HttpResponse.json(makeRoutine({ id: 77, penalty: "0.10" }));
    }),
  );
  const result = await saveScores({
    routineId: undefined,
    entryId: 9,
    apparatus: "hoop",
    boxes,
    existing: [],
    values: { dBody: 7.3, e1: 8.25 },
    penalty: 0.1,
    currentPenalty: 0,
  });
  expect(result.routineId).toBe(77);
  expect(result.boxErrors).toEqual({});
  expect(posted).toEqual([
    { routine_id: 77, judge_id: 1, panel: "difficulty_body", value: "7.30" },
    { routine_id: 77, judge_id: 2, panel: "execution", value: "8.25" },
  ]);
  expect(patchedPenalty).toEqual({ penalty: "0.10" });
});

test("a failing routine create reports a form-level error, not a box error", async () => {
  server.use(
    http.post(api("/routines/"), () =>
      HttpResponse.json({ detail: "meet is completed" }, { status: 409 }),
    ),
  );
  const result = await saveScores({
    routineId: undefined,
    entryId: 9,
    apparatus: "hoop",
    boxes,
    existing: [],
    values: { dBody: 7.3 },
    penalty: 0,
    currentPenalty: 0,
  });
  expect(result).toEqual({
    routineId: null,
    boxErrors: {},
    formError: "meet is completed",
  });
});

test("a failing box reports its error while others succeed", async () => {
  server.use(
    http.post(api("/judge-scores/"), async ({ request }) => {
      const body = (await request.json()) as { panel: string };
      if (body.panel === "execution") {
        return HttpResponse.json({ detail: "meet is completed" }, { status: 409 });
      }
      return HttpResponse.json({}, { status: 201 });
    }),
  );
  const result = await saveScores({
    routineId: 77,
    entryId: 9,
    apparatus: "hoop",
    boxes,
    existing: [],
    values: { dBody: 7.3, e1: 8.25 },
    penalty: undefined,
    currentPenalty: 0,
  });
  expect(result.boxErrors).toEqual({ e1: "meet is completed" });
});

test("unchanged penalty is not PATCHed", async () => {
  let patched = false;
  server.use(
    http.patch(api("/routines/:routineId"), () => {
      patched = true;
      return HttpResponse.json(makeRoutine({ id: 77 }));
    }),
  );
  const result = await saveScores({
    routineId: 77,
    entryId: 9,
    apparatus: "hoop",
    boxes,
    existing: [],
    values: {},
    penalty: undefined,
    currentPenalty: 0,
  });
  expect(result.boxErrors).toEqual({});
  expect(patched).toBe(false);
});

test("undefined penalty on a routine with an existing nonzero penalty is left alone (locked case)", async () => {
  let patched = false;
  server.use(
    http.patch(api("/routines/:routineId"), () => {
      patched = true;
      return HttpResponse.json(makeRoutine({ id: 77, penalty: "0.30" }));
    }),
  );
  const result = await saveScores({
    routineId: 77,
    entryId: 9,
    apparatus: "hoop",
    boxes,
    existing: [],
    values: {},
    penalty: undefined,
    currentPenalty: 0.3,
  });
  expect(result.boxErrors).toEqual({});
  expect(patched).toBe(false);
});
