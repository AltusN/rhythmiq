import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeMeet } from "../../fixtures";
import { api, server } from "../../msw/server";
import { renderApp } from "../../utils";

function mockMeet(meet: ReturnType<typeof makeMeet>) {
  server.use(
    http.get(api("/meets/:meetId"), () => HttpResponse.json(meet)),
    http.get(api("/districts/"), () => HttpResponse.json([])),
    http.get(api("/meets/:meetId/standings"), () =>
      HttpResponse.json({
        meet_id: meet.id,
        provisional: true,
        apparatus: "hoop",
        level: null,
        age_group: null,
        rankings: [],
      }),
    ),
    http.get(api("/meets/:meetId/all-around"), () =>
      HttpResponse.json({
        meet_id: meet.id,
        provisional: true,
        level: null,
        age_group: null,
        rankings: [],
      }),
    ),
  );
}

test("draft meet offers Schedule and Cancel only", async () => {
  mockMeet(makeMeet({ id: 5, status: "draft" }));
  renderApp("/meets/5/standings");
  await screen.findByText("Winter Cup");
  expect(screen.getByRole("button", { name: "Schedule" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancel meet" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Complete meet" })).toBeNull();
});

test("completed meet offers no transitions", async () => {
  mockMeet(makeMeet({ id: 5, status: "completed" }));
  renderApp("/meets/5/standings");
  await screen.findByText("Winter Cup");
  expect(screen.queryByRole("button", { name: /meet|Schedule/ })).toBeNull();
});

test("completing asks for confirmation and PATCHes status", async () => {
  mockMeet(makeMeet({ id: 5, status: "in_progress" }));
  let patched: unknown = null;
  server.use(
    http.patch(api("/meets/:meetId"), async ({ request }) => {
      patched = await request.json();
      return HttpResponse.json(makeMeet({ id: 5, status: "completed" }));
    }),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/meets/5/standings");
  await userEvent.click(await screen.findByRole("button", { name: "Complete meet" }));
  expect(confirmSpy).toHaveBeenCalled();
  await waitFor(() => expect(patched).toEqual({ status: "completed" }));
  confirmSpy.mockRestore();
});

test("shows API detail when a transition is rejected", async () => {
  mockMeet(makeMeet({ id: 5, status: "in_progress" }));
  server.use(
    http.patch(api("/meets/:meetId"), () =>
      HttpResponse.json(
        { detail: "Invalid status transition from in_progress to scheduled." },
        { status: 409 },
      ),
    ),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/meets/5/standings");
  await userEvent.click(await screen.findByRole("button", { name: "Complete meet" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Invalid status transition",
  );
  confirmSpy.mockRestore();
});

test("edits meet details from the header without sending status", async () => {
  server.use(
    http.get(api("/meets/4"), () =>
      HttpResponse.json(makeMeet({ id: 4, name: "Spring Open", status: "scheduled" })),
    ),
  );
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  server.use(http.get(api("/meet-entries/"), () => HttpResponse.json([])));
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/meets/4"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeMeet({ id: 4, name: "Spring Classic" }));
    }),
  );
  renderApp("/meets/4/scoring");
  await userEvent.click(await screen.findByRole("button", { name: "Edit details" }));
  const dialog = within(screen.getByRole("dialog"));
  const name = dialog.getByLabelText("Name");
  await userEvent.clear(name);
  await userEvent.type(name, "Spring Classic");
  await userEvent.click(dialog.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ name: "Spring Classic" }));
});

test("the details dialog offers no status control", async () => {
  server.use(
    http.get(api("/meets/4"), () =>
      HttpResponse.json(makeMeet({ id: 4, name: "Spring Open", status: "scheduled" })),
    ),
  );
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  server.use(http.get(api("/meet-entries/"), () => HttpResponse.json([])));
  renderApp("/meets/4/scoring");
  await userEvent.click(await screen.findByRole("button", { name: "Edit details" }));
  const dialog = within(screen.getByRole("dialog"));
  expect(await dialog.findByLabelText("Name")).toBeInTheDocument();
  expect(dialog.queryByLabelText("Status")).not.toBeInTheDocument();
});

test("editing meet details invalidates standings, since medal minima feed medal_for_total", async () => {
  let standingsCalls = 0;
  server.use(
    http.get(api("/meets/5"), () =>
      HttpResponse.json(makeMeet({ id: 5, name: "Winter Cup", status: "scheduled" })),
    ),
    http.get(api("/districts/"), () => HttpResponse.json([])),
    http.get(api("/meets/5/standings"), () => {
      standingsCalls += 1;
      return HttpResponse.json({
        meet_id: 5,
        provisional: true,
        apparatus: "hoop",
        level: null,
        age_group: null,
        rankings: [],
      });
    }),
    http.get(api("/meets/5/all-around"), () =>
      HttpResponse.json({ meet_id: 5, provisional: true, level: null, age_group: null, rankings: [] }),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/meets/5"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(
        makeMeet({ id: 5, name: "Winter Cup", medal_gold_min: "9.5", medal_silver_min: "8.5" }),
      );
    }),
  );
  renderApp("/meets/5/standings");
  await screen.findByText("Winter Cup");
  await waitFor(() => expect(standingsCalls).toBe(1));

  await userEvent.click(await screen.findByRole("button", { name: "Edit details" }));
  const dialog = within(screen.getByRole("dialog"));
  await userEvent.type(dialog.getByLabelText("Gold minimum"), "9.5");
  await userEvent.type(dialog.getByLabelText("Silver minimum"), "8.5");
  await userEvent.click(dialog.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(patched).toEqual({ medal_gold_min: 9.5, medal_silver_min: 8.5 }),
  );

  // The medal minima just changed, which changes every standings row's medal tier
  // (backend/app/scoring.py:medal_for_total) -- the already-mounted standings query
  // must be invalidated and refetched, not left showing tiers computed under the
  // old cutoffs.
  await waitFor(() => expect(standingsCalls).toBe(2));
});
