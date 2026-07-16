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

test("invalid step shows a field error and blocks save", async () => {
  mockBase();
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("E1"), "8.27");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText(/0\.05/)).toBeInTheDocument();
});

test("unassigned slots render disabled boxes", async () => {
  mockBase();
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  expect(await screen.findByLabelText("E2")).toBeDisabled();
  expect(screen.getByLabelText("Artistry")).toBeDisabled();
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

test("completed meet renders the form read-only", async () => {
  mockBase({ meet: makeMeet({ id: 5, status: "completed" }) });
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  expect(await screen.findByLabelText("E1")).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
});
