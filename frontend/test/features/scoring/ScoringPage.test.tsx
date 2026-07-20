import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { savePanel } from "../../../src/features/scoring/panel-storage";
import {
  makeEntry,
  makeGymnast,
  makeJudge,
  makeMeet,
  makeRoutine,
  makeScore,
} from "../../fixtures";
import { api, server } from "../../msw/server";
import { renderApp } from "../../utils";

const gymnast = makeGymnast({ id: 7, first_name: "Aletta", last_name: "van der Merwe" });
const seniorEntry = makeEntry({ id: 21, meet_id: 5, gymnast_id: 7, group_id: null, level: "senior", bib_number: "12" });

function mockBase({
  meet = makeMeet({ id: 5, status: "in_progress" }),
  entries = [seniorEntry],
  routines = [] as unknown[],
  scores = [] as unknown[],
  penaltyRecords = [] as unknown[],
} = {}) {
  server.use(
    http.get(api("/meets/:meetId"), () => HttpResponse.json(meet)),
    http.get(api("/districts/"), () => HttpResponse.json([])),
    http.get(api("/meet-entries/"), () => HttpResponse.json(entries)),
    http.get(api("/gymnasts/"), () => HttpResponse.json([gymnast])),
    http.get(api("/groups/"), () => HttpResponse.json([])),
    http.get(api("/judges/"), () =>
      HttpResponse.json([
        makeJudge({ id: 1, first_name: "Naledi", last_name: "Dlamini" }),
        makeJudge({ id: 2, first_name: "Mina", last_name: "Kim" }),
      ]),
    ),
    http.get(api("/routines/"), () => HttpResponse.json(routines)),
    http.get(api("/judge-scores/"), () => HttpResponse.json(scores)),
    http.get(api("/penalty-records/"), () => HttpResponse.json(penaltyRecords)),
    http.get(api("/meets/:meetId/standings"), () =>
      HttpResponse.json({
        meet_id: 5,
        provisional: true,
        apparatus: "hoop",
        level: null,
        age_group: null,
        rankings: [],
      }),
    ),
  );
}

beforeEach(() => {
  localStorage.clear();
  savePanel(5, { D: 1, E1: 2 });
});

test("selecting a senior competitor shows all boxes; E-only level hides D and A", async () => {
  const level5Entry = makeEntry({ id: 22, meet_id: 5, gymnast_id: 7, group_id: null, level: "level_5", bib_number: "13" });
  mockBase({ entries: [seniorEntry, level5Entry] });
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  expect(await screen.findByLabelText("D-Body")).toBeInTheDocument();
  expect(screen.getByLabelText("Artistry")).toBeInTheDocument();
  expect(screen.getByLabelText("E1")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: /13 ·/ }));
  await waitFor(() => expect(screen.queryByLabelText("D-Body")).toBeNull());
  expect(screen.getByLabelText("E1")).toBeInTheDocument();
});

test("save lazily creates the routine and posts scores", async () => {
  mockBase();
  let routinePosted: unknown = null;
  const scoresPosted: unknown[] = [];
  server.use(
    http.post(api("/routines/"), async ({ request }) => {
      routinePosted = await request.json();
      return HttpResponse.json(makeRoutine({ id: 77, entry_id: 21 }), { status: 201 });
    }),
    http.post(api("/judge-scores/"), async ({ request }) => {
      scoresPosted.push(await request.json());
      return HttpResponse.json({}, { status: 201 });
    }),
  );
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("D-Body"), "7.30");
  await userEvent.type(screen.getByLabelText("E1"), "8.25");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(routinePosted).toEqual({ entry_id: 21, apparatus: "hoop" }));
  await waitFor(() => expect(scoresPosted).toHaveLength(2));
});

test("a partial failure during lazy routine creation keeps the box error and value after the routine refetch", async () => {
  mockBase();
  let createdRoutine: ReturnType<typeof makeRoutine> | null = null;
  server.use(
    http.get(api("/routines/"), () =>
      HttpResponse.json(createdRoutine ? [createdRoutine] : []),
    ),
    http.post(api("/routines/"), async () => {
      createdRoutine = makeRoutine({ id: 77, entry_id: 21 });
      return HttpResponse.json(createdRoutine, { status: 201 });
    }),
    http.post(api("/judge-scores/"), async ({ request }) => {
      const body = (await request.json()) as { panel: string };
      if (body.panel === "execution") {
        return HttpResponse.json({ detail: "boom" }, { status: 409 });
      }
      return HttpResponse.json({}, { status: 201 });
    }),
  );
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("D-Body"), "7.30");
  await userEvent.type(screen.getByLabelText("E1"), "8.25");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("boom")).toBeInTheDocument();
  expect(screen.getByLabelText("E1")).toHaveValue("8.25");
});

test("invalid step shows a field error and blocks save", async () => {
  mockBase();
  let posted = false;
  server.use(
    http.post(api("/routines/"), () => {
      posted = true;
      return HttpResponse.json(makeRoutine({ id: 77, entry_id: 21 }), { status: 201 });
    }),
    http.post(api("/judge-scores/"), () => {
      posted = true;
      return HttpResponse.json({}, { status: 201 });
    }),
  );
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("E1"), "8.27");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Use 0.05 steps")).toBeInTheDocument();
  expect(posted).toBe(false);
});

test("unparseable input never renders NaN in the preview", async () => {
  mockBase();
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("E1"), "8,25");
  expect(screen.queryByText(/NaN/)).toBeNull();
});

test("loaded scores and penalty render with two decimals", async () => {
  const routine = makeRoutine({ id: 77, entry_id: 21, penalty: "0.30" });
  mockBase({
    routines: [routine],
    scores: [makeScore({ routine_id: 77, judge_id: 2, panel: "execution", value: "8.40" })],
  });
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  expect(await screen.findByLabelText("E1")).toHaveValue("8.40");
  expect(screen.getByLabelText("Penalty")).toHaveValue("0.30");
});

test("unassigned slots render disabled boxes", async () => {
  mockBase();
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  expect(await screen.findByLabelText("E2")).toBeDisabled();
  expect(screen.getByLabelText("Artistry")).toBeDisabled();
});

test("the first enabled box is focused when a competitor is picked", async () => {
  mockBase();
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  expect(await screen.findByLabelText("D-Body")).toHaveFocus();
});

test("E-only levels focus E1 on mount", async () => {
  const level5Entry = makeEntry({ id: 22, meet_id: 5, gymnast_id: 7, group_id: null, level: "level_5", bib_number: "13" });
  mockBase({ entries: [level5Entry] });
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /13 ·/ }));
  expect(await screen.findByLabelText("E1")).toHaveFocus();
});

test("a disabled first slot is skipped when focusing", async () => {
  savePanel(5, { E1: 2 }); // no D judge: D-Body/D-App render disabled
  mockBase();
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  expect(await screen.findByLabelText("D-Body")).toBeDisabled();
  expect(screen.getByLabelText("E1")).toHaveFocus();
});

test("a clean save shows the Saved ✓ indicator; the next edit clears it", async () => {
  mockBase();
  server.use(
    http.post(api("/routines/"), () =>
      HttpResponse.json(makeRoutine({ id: 77, entry_id: 21 }), { status: 201 }),
    ),
    http.post(api("/judge-scores/"), () => HttpResponse.json({}, { status: 201 })),
  );
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("E1"), "8.25");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Saved ✓")).toBeInTheDocument();

  await userEvent.type(screen.getByLabelText("E1"), "5");
  expect(screen.queryByText("Saved ✓")).toBeNull();
});

test("a save that returns a box error shows no Saved ✓", async () => {
  mockBase({ routines: [makeRoutine({ id: 77, entry_id: 21 })] });
  server.use(
    http.post(api("/judge-scores/"), () =>
      HttpResponse.json({ detail: "boom" }, { status: 409 }),
    ),
  );
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("E1"), "8.25");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("boom")).toBeInTheDocument();
  expect(screen.queryByText("Saved ✓")).toBeNull();
});

test("the age-group filter reaches the API and clears the selection", async () => {
  mockBase();
  let seenAgeGroup: string | null = null;
  server.use(
    http.get(api("/meet-entries/"), ({ request }) => {
      seenAgeGroup = new URL(request.url).searchParams.get("age_group");
      return HttpResponse.json([seniorEntry]);
    }),
  );
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await screen.findByLabelText("D-Body");
  await userEvent.selectOptions(screen.getByLabelText("Age group filter"), "o14");
  await waitFor(() => expect(seenAgeGroup).toBe("o14"));
  expect(await screen.findByText("Pick a competitor to score.")).toBeInTheDocument();
});

test("the apparatus select reaches the API and clears the selection", async () => {
  // Apparatus is not a filter — it's half the key the lazily-created Routine is
  // keyed on — so it lives in its own row above the level/age filters. This pins
  // that moving it kept it wired to both the standings query and the selection reset.
  mockBase();
  let seenApparatus: string | null = null;
  server.use(
    http.get(api("/meets/:meetId/standings"), ({ request }) => {
      seenApparatus = new URL(request.url).searchParams.get("apparatus");
      return HttpResponse.json({ meet_id: 5, provisional: true, rows: [] });
    }),
  );
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await screen.findByLabelText("D-Body");
  await userEvent.selectOptions(screen.getByLabelText("Apparatus"), "ribbon");
  await waitFor(() => expect(seenApparatus).toBe("ribbon"));
  expect(await screen.findByText("Pick a competitor to score.")).toBeInTheDocument();
});

test("penalty box locks when itemized penalty records exist", async () => {
  const routine = makeRoutine({ id: 77, entry_id: 21, penalty: "0.30" });
  mockBase({
    routines: [routine],
    scores: [makeScore({ routine_id: 77, judge_id: 2, panel: "execution", value: "8.00" })],
    penaltyRecords: [{ id: 1, routine_id: 77, judge_id: 1, judge_role: "line_judge", description: "boundary touch", amount: "0.30" }],
  });
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  expect(await screen.findByLabelText("Penalty")).toBeDisabled();
});

test("panel footer shows full judge names and a hint offers setup for missing required slots", async () => {
  mockBase();
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await screen.findByLabelText("D-Body");
  expect(screen.getByText(/Naledi Dlamini/)).toBeInTheDocument();
  // default panel { D: 1, E1: 2 }: A and E2 are required but unassigned
  const hint = screen.getByRole("button", { name: "Assign judges…" });
  await userEvent.click(hint);
  expect(screen.getByRole("button", { name: "Save panel" })).toBeInTheDocument();
});

test("no hint when the minimum viable panel is assigned, even with E3/E4 empty", async () => {
  savePanel(5, { D: 1, A: 1, E1: 2, E2: 1 });
  mockBase();
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await screen.findByLabelText("D-Body");
  expect(screen.queryByRole("button", { name: "Assign judges…" })).toBeNull();
});

test("E-only levels do not warn about unassigned D/A slots", async () => {
  savePanel(5, { E1: 2, E2: 1 });
  const level5Entry = makeEntry({ id: 22, meet_id: 5, gymnast_id: 7, group_id: null, level: "level_5", bib_number: "13" });
  mockBase({ entries: [level5Entry] });
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /13 ·/ }));
  await screen.findByLabelText("E1");
  expect(screen.queryByRole("button", { name: "Assign judges…" })).toBeNull();
});

test("switching competitors with unsaved edits prompts; declining keeps the form", async () => {
  const second = makeEntry({ id: 22, meet_id: 5, gymnast_id: 7, group_id: null, level: "senior", bib_number: "13" });
  mockBase({ entries: [seniorEntry, second] });
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("E1"), "8.25");
  await userEvent.click(screen.getByRole("button", { name: /13 ·/ }));
  expect(confirmSpy).toHaveBeenCalledWith("Discard unsaved scores?");
  expect(screen.getByLabelText("E1")).toHaveValue("8.25"); // still bib 12's form

  confirmSpy.mockReturnValue(true);
  await userEvent.click(screen.getByRole("button", { name: /13 ·/ }));
  await waitFor(() => expect(screen.getByLabelText("E1")).toHaveValue(""));
  confirmSpy.mockRestore();
});

test("a clean save clears dirtiness, so switching does not prompt", async () => {
  const second = makeEntry({ id: 22, meet_id: 5, gymnast_id: 7, group_id: null, level: "senior", bib_number: "13" });
  mockBase({ entries: [seniorEntry, second] });
  server.use(
    http.post(api("/routines/"), () =>
      HttpResponse.json(makeRoutine({ id: 77, entry_id: 21 }), { status: 201 }),
    ),
    http.post(api("/judge-scores/"), () => HttpResponse.json({}, { status: 201 })),
  );
  const confirmSpy = vi.spyOn(window, "confirm");
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("E1"), "8.25");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByText("Saved ✓");
  await userEvent.click(screen.getByRole("button", { name: /13 ·/ }));
  expect(confirmSpy).not.toHaveBeenCalled();
  confirmSpy.mockRestore();
});

test("completed meet renders the form read-only", async () => {
  mockBase({ meet: makeMeet({ id: 5, status: "completed" }) });
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  expect(await screen.findByLabelText("E1")).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
});

test("routine-create failure reports a form-level error, not a penalty error", async () => {
  mockBase();
  server.use(
    http.post(api("/routines/"), () =>
      HttpResponse.json({ detail: "meet is completed" }, { status: 409 }),
    ),
  );
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("E1"), "8.25");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("meet is completed");
  expect(
    screen.getByLabelText("Penalty").parentElement?.textContent,
  ).not.toContain("meet is completed");
});

test("a failed gymnasts query surfaces an error instead of silently numbering competitors", async () => {
  mockBase();
  server.use(
    http.get(api("/gymnasts/"), () =>
      HttpResponse.json({ detail: "gymnasts down" }, { status: 500 }),
    ),
  );
  renderApp("/meets/5/scoring");
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("gymnasts down");
});

test("a failing refetch after save surfaces an error while the form stays mounted", async () => {
  mockBase();
  let createdRoutine: ReturnType<typeof makeRoutine> | null = null;
  server.use(
    http.get(api("/routines/"), () =>
      HttpResponse.json(createdRoutine ? [createdRoutine] : []),
    ),
    http.post(api("/routines/"), () => {
      createdRoutine = makeRoutine({ id: 77, entry_id: 21 });
      return HttpResponse.json(createdRoutine, { status: 201 });
    }),
    // scoresQ is disabled until the routine exists, so this only ever serves the
    // post-save refetch -- which fails
    http.get(api("/judge-scores/"), () =>
      HttpResponse.json({ detail: "db down" }, { status: 500 }),
    ),
    http.post(api("/judge-scores/"), () => HttpResponse.json({}, { status: 201 })),
  );
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("E1"), "8.25");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("db down");
  expect(screen.getByLabelText("E1")).toHaveValue("8.25");
});

test("a failed routines query surfaces an error instead of hanging on Loading", async () => {
  mockBase();
  server.use(
    http.get(api("/routines/"), () =>
      HttpResponse.json({ detail: "db down" }, { status: 500 }),
    ),
  );
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("db down");
  expect(screen.queryByText("Loading…")).toBeNull();
});

test("the unassigned warning says REQUIRED, and the panel line marks E3/E4 optional", async () => {
  // beforeEach assigns only D and E1, so A and E2 are the outstanding REQUIRED slots.
  // E3/E4 are optional extra Execution judges and must NOT appear in the warning --
  // without the word "Required" that list reads as contradicting the panel summary
  // below it, which lists all six slots.
  mockBase();
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));

  const warning = await screen.findByText(/Required judge slots unassigned/);
  expect(warning).toHaveTextContent("Required judge slots unassigned: A, E2.");
  expect(warning).not.toHaveTextContent("E3");
  expect(warning).not.toHaveTextContent("E4");

  expect(screen.getByText(/^Panel:/)).toHaveTextContent("E3 (optional)");
  expect(screen.getByText(/^Panel:/)).toHaveTextContent("E4 (optional)");
});

test("a zero penalty renders unsigned, not as negative zero", async () => {
  mockBase();
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));

  const summary = await screen.findByText(/^Penalty:/);
  expect(summary).toHaveTextContent("Penalty: 0.00");
  expect(summary).not.toHaveTextContent("−0.00");
});
