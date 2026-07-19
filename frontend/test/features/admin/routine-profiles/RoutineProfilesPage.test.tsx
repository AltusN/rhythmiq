import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeGroup, makeGymnast, makeRoutineProfile } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

function seedOwners() {
  server.use(
    http.get(api("/gymnasts/"), () =>
      HttpResponse.json([makeGymnast({ id: 1, first_name: "Ana", last_name: "Meyer" })]),
    ),
  );
  server.use(
    http.get(api("/groups/"), () => HttpResponse.json([makeGroup({ id: 9, name: "Junior Team A" })])),
  );
}

test("lists profiles with resolved owner names", async () => {
  seedOwners();
  server.use(
    http.get(api("/routine-profiles/"), () =>
      HttpResponse.json([
        makeRoutineProfile({ id: 1, gymnast_id: 1, group_id: null, apparatus: "ribbon", level: "level_3" }),
        makeRoutineProfile({ id: 2, gymnast_id: null, group_id: 9, apparatus: "hoop", level: "level_2" }),
      ]),
    ),
  );
  renderApp("/admin/routine-profiles");
  expect(await screen.findByText("Ana Meyer")).toBeInTheDocument();
  expect(screen.getByText("Junior Team A")).toBeInTheDocument();
});

test("shows an empty message when there are no profiles", async () => {
  seedOwners();
  server.use(http.get(api("/routine-profiles/"), () => HttpResponse.json([])));
  renderApp("/admin/routine-profiles");
  expect(await screen.findByText("No routine profiles yet.")).toBeInTheDocument();
});

test("surfaces a list error", async () => {
  seedOwners();
  server.use(
    http.get(api("/routine-profiles/"), () =>
      HttpResponse.json({ detail: "Database unavailable" }, { status: 500 }),
    ),
  );
  renderApp("/admin/routine-profiles");
  expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable");
});

test("creates a gymnast profile, sending group_id null", async () => {
  seedOwners();
  server.use(http.get(api("/routine-profiles/"), () => HttpResponse.json([])));
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/routine-profiles/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeRoutineProfile(), { status: 201 });
    }),
  );
  renderApp("/admin/routine-profiles");
  await userEvent.click(await screen.findByRole("button", { name: "New routine profile" }));
  await waitFor(() =>
    expect(within(screen.getByRole("dialog")).getByText("Ana Meyer")).toBeInTheDocument(),
  );
  await userEvent.selectOptions(screen.getByLabelText("Gymnast"), "1");
  await userEvent.selectOptions(
    within(screen.getByRole("dialog")).getByLabelText("Apparatus"),
    "ribbon",
  );
  await userEvent.selectOptions(screen.getByLabelText("Level"), "level_3");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({
      gymnast_id: 1,
      group_id: null,
      apparatus: "ribbon",
      level: "level_3",
      music_url: null,
      choreography_notes: null,
    }),
  );
});

test("switching owner kind to Group sends gymnast_id null", async () => {
  seedOwners();
  server.use(http.get(api("/routine-profiles/"), () => HttpResponse.json([])));
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/routine-profiles/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeRoutineProfile(), { status: 201 });
    }),
  );
  renderApp("/admin/routine-profiles");
  await userEvent.click(await screen.findByRole("button", { name: "New routine profile" }));
  await waitFor(() =>
    expect(within(screen.getByRole("dialog")).getByText("Ana Meyer")).toBeInTheDocument(),
  );
  await userEvent.selectOptions(screen.getByLabelText("Gymnast"), "1");
  await userEvent.click(screen.getByLabelText("Group"));
  await waitFor(() => expect(screen.getByLabelText("Group name")).toBeInTheDocument());
  await userEvent.selectOptions(screen.getByLabelText("Group name"), "9");
  await userEvent.selectOptions(
    within(screen.getByRole("dialog")).getByLabelText("Apparatus"),
    "hoop",
  );
  await userEvent.selectOptions(screen.getByLabelText("Level"), "level_2");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({
      gymnast_id: null,
      group_id: 9,
      apparatus: "hoop",
      level: "level_2",
      music_url: null,
      choreography_notes: null,
    }),
  );
});

test("blocks submission when no owner is picked", async () => {
  seedOwners();
  server.use(http.get(api("/routine-profiles/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/routine-profiles/"), () => {
      called = true;
      return HttpResponse.json(makeRoutineProfile(), { status: 201 });
    }),
  );
  renderApp("/admin/routine-profiles");
  await userEvent.click(await screen.findByRole("button", { name: "New routine profile" }));
  await userEvent.selectOptions(
    within(screen.getByRole("dialog")).getByLabelText("Apparatus"),
    "ribbon",
  );
  await userEvent.selectOptions(screen.getByLabelText("Level"), "level_3");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Pick a gymnast or group")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("blocks choreography notes over 500 characters", async () => {
  seedOwners();
  server.use(http.get(api("/routine-profiles/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/routine-profiles/"), () => {
      called = true;
      return HttpResponse.json(makeRoutineProfile(), { status: 201 });
    }),
  );
  renderApp("/admin/routine-profiles");
  await userEvent.click(await screen.findByRole("button", { name: "New routine profile" }));
  await waitFor(() =>
    expect(within(screen.getByRole("dialog")).getByText("Ana Meyer")).toBeInTheDocument(),
  );
  await userEvent.selectOptions(screen.getByLabelText("Gymnast"), "1");
  await userEvent.selectOptions(
    within(screen.getByRole("dialog")).getByLabelText("Apparatus"),
    "ribbon",
  );
  await userEvent.selectOptions(screen.getByLabelText("Level"), "level_3");
  const notes = screen.getByLabelText("Choreography notes");
  await userEvent.click(notes);
  await userEvent.paste("x".repeat(501));
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("At most 500 characters")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("shows the 409 detail on a duplicate profile", async () => {
  seedOwners();
  server.use(http.get(api("/routine-profiles/"), () => HttpResponse.json([])));
  server.use(
    http.post(api("/routine-profiles/"), () =>
      HttpResponse.json({ detail: "Routine profile already exists" }, { status: 409 }),
    ),
  );
  renderApp("/admin/routine-profiles");
  await userEvent.click(await screen.findByRole("button", { name: "New routine profile" }));
  await waitFor(() =>
    expect(within(screen.getByRole("dialog")).getByText("Ana Meyer")).toBeInTheDocument(),
  );
  await userEvent.selectOptions(screen.getByLabelText("Gymnast"), "1");
  await userEvent.selectOptions(
    within(screen.getByRole("dialog")).getByLabelText("Apparatus"),
    "ribbon",
  );
  await userEvent.selectOptions(screen.getByLabelText("Level"), "level_3");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Routine profile already exists")).toBeInTheDocument();
});

test("filters by apparatus as a server round trip", async () => {
  seedOwners();
  const seen: (string | null)[] = [];
  server.use(
    http.get(api("/routine-profiles/"), ({ request }) => {
      seen.push(new URL(request.url).searchParams.get("apparatus"));
      return HttpResponse.json([makeRoutineProfile({ id: 1, gymnast_id: 1, group_id: null })]);
    }),
  );
  renderApp("/admin/routine-profiles");
  expect(await screen.findByText("Ana Meyer")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Apparatus filter"), "hoop");
  await waitFor(() => expect(seen).toContain("hoop"));
});

test("search filters rows client-side without refetching", async () => {
  seedOwners();
  let calls = 0;
  server.use(
    http.get(api("/routine-profiles/"), () => {
      calls += 1;
      return HttpResponse.json([
        makeRoutineProfile({ id: 1, gymnast_id: 1, group_id: null }),
        makeRoutineProfile({ id: 2, gymnast_id: null, group_id: 9 }),
      ]);
    }),
  );
  renderApp("/admin/routine-profiles");
  expect(await screen.findByText("Ana Meyer")).toBeInTheDocument();
  const before = calls;
  await userEvent.type(screen.getByLabelText("Search"), "Junior");
  await waitFor(() => expect(screen.queryByText("Ana Meyer")).not.toBeInTheDocument());
  expect(screen.getByText("Junior Team A")).toBeInTheDocument();
  expect(calls).toBe(before);
});
