import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import App from "../../../src/App";
import { makeDistrict, makeMeet } from "../../fixtures";
import { api, server } from "../../msw/server";
import { renderApp } from "../../utils";

/**
 * Like `renderApp`, but with a caller-supplied QueryClient so a test can share one
 * client across two separate mounts (e.g. visit the meet detail page, navigate away,
 * edit from the list, then revisit) -- the only way to prove a cache invalidation
 * actually happened rather than relying on `staleTime: 0` refetching on every mount
 * regardless of whether anything was invalidated.
 */
function renderAppWithClient(route: string, queryClient: QueryClient) {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function seedDistricts() {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([makeDistrict({ id: 1, name: "Western Cape", abbreviation: "WC" })]),
    ),
  );
}

test("lists meets with status badges", async () => {
  server.use(
    http.get(api("/meets/"), () =>
      HttpResponse.json([
        makeMeet({ name: "Winter Cup", status: "in_progress" }),
        makeMeet({ name: "Spring Trials", status: "draft" }),
      ]),
    ),
  );
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  renderApp("/");
  expect(await screen.findByText("Winter Cup")).toBeInTheDocument();
  expect(screen.getByText("Spring Trials")).toBeInTheDocument();
  expect(screen.getByText("in progress")).toBeInTheDocument();
  expect(screen.getByText("draft")).toBeInTheDocument();
});

test("shows the API error detail on failure", async () => {
  server.use(
    http.get(api("/meets/"), () =>
      HttpResponse.json({ detail: "boom" }, { status: 500 }),
    ),
  );
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  renderApp("/");
  expect(await screen.findByRole("alert")).toHaveTextContent("boom");
});

test("meet name still navigates into the meet", async () => {
  seedDistricts();
  server.use(
    http.get(api("/meets/"), () => HttpResponse.json([makeMeet({ id: 4, name: "Spring Open" })])),
  );
  server.use(http.get(api("/meets/4"), () => HttpResponse.json(makeMeet({ id: 4, name: "Spring Open" }))));
  server.use(http.get(api("/meet-entries/"), () => HttpResponse.json([])));
  renderApp("/");
  await userEvent.click(await screen.findByRole("link", { name: /Spring Open/ }));
  expect(await screen.findByRole("heading", { name: /Spring Open/ })).toBeInTheDocument();
});

test("creates a meet without sending status", async () => {
  seedDistricts();
  server.use(http.get(api("/meets/"), () => HttpResponse.json([])));
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/meets/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeMeet(), { status: 201 });
    }),
  );
  renderApp("/");
  await userEvent.click(await screen.findByRole("button", { name: "New meet" }));
  await userEvent.type(screen.getByLabelText("Name"), "Spring Open");
  await userEvent.type(screen.getByLabelText("Location"), "Cape Town");
  await userEvent.type(screen.getByLabelText("Start date"), "2026-09-01");
  await userEvent.type(screen.getByLabelText("End date"), "2026-09-02");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({
      name: "Spring Open",
      location: "Cape Town",
      start_date: "2026-09-01",
      end_date: "2026-09-02",
      district_id: null,
      medal_gold_min: null,
      medal_silver_min: null,
    }),
  );
  expect(posted!).not.toHaveProperty("status");
});

test("edits a meet, pre-filled from the existing row, sending only the changed field", async () => {
  seedDistricts();
  server.use(
    http.get(api("/meets/"), () =>
      HttpResponse.json([
        makeMeet({
          id: 4,
          name: "Spring Open",
          location: "Cape Town",
          start_date: "2026-09-01",
          end_date: "2026-09-02",
          district_id: null,
          medal_gold_min: null,
          medal_silver_min: null,
        }),
      ]),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/meets/:meetId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeMeet({ id: 4, name: "Spring Open", location: "Durban" }));
    }),
  );
  renderApp("/");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Spring Open" }));
  const dialog = within(screen.getByRole("dialog"));
  expect(dialog.getByLabelText("Name")).toHaveValue("Spring Open");
  await userEvent.clear(dialog.getByLabelText("Location"));
  await userEvent.type(dialog.getByLabelText("Location"), "Durban");
  await userEvent.click(dialog.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ location: "Durban" }));
});

test("blocks an end date before the start date", async () => {
  seedDistricts();
  server.use(http.get(api("/meets/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/meets/"), () => {
      called = true;
      return HttpResponse.json(makeMeet(), { status: 201 });
    }),
  );
  renderApp("/");
  await userEvent.click(await screen.findByRole("button", { name: "New meet" }));
  await userEvent.type(screen.getByLabelText("Name"), "Spring Open");
  await userEvent.type(screen.getByLabelText("Location"), "Cape Town");
  await userEvent.type(screen.getByLabelText("Start date"), "2026-09-05");
  await userEvent.type(screen.getByLabelText("End date"), "2026-09-01");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("End date must be on or after the start date")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("blocks a gold minimum that is not above the silver minimum", async () => {
  seedDistricts();
  server.use(http.get(api("/meets/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/meets/"), () => {
      called = true;
      return HttpResponse.json(makeMeet(), { status: 201 });
    }),
  );
  renderApp("/");
  await userEvent.click(await screen.findByRole("button", { name: "New meet" }));
  await userEvent.type(screen.getByLabelText("Name"), "Spring Open");
  await userEvent.type(screen.getByLabelText("Location"), "Cape Town");
  await userEvent.type(screen.getByLabelText("Start date"), "2026-09-01");
  await userEvent.type(screen.getByLabelText("End date"), "2026-09-02");
  await userEvent.type(screen.getByLabelText("Gold minimum"), "8");
  await userEvent.type(screen.getByLabelText("Silver minimum"), "9");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Gold minimum must be above silver")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("blocks setting only one medal minimum", async () => {
  seedDistricts();
  server.use(http.get(api("/meets/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/meets/"), () => {
      called = true;
      return HttpResponse.json(makeMeet(), { status: 201 });
    }),
  );
  renderApp("/");
  await userEvent.click(await screen.findByRole("button", { name: "New meet" }));
  await userEvent.type(screen.getByLabelText("Name"), "Spring Open");
  await userEvent.type(screen.getByLabelText("Location"), "Cape Town");
  await userEvent.type(screen.getByLabelText("Start date"), "2026-09-01");
  await userEvent.type(screen.getByLabelText("End date"), "2026-09-02");
  await userEvent.type(screen.getByLabelText("Gold minimum"), "9");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Set both medal minimums or neither")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("editing a meet from the list invalidates its cached detail and standings, so revisiting isn't stale", async () => {
  // A non-zero staleTime is essential here: with the default staleTime: 0, a
  // remount always refetches regardless of invalidation, which would make this
  // test pass even without the fix. Only an explicit invalidateQueries call
  // (not staleness) can force TanStack Query to refetch a query mounted under
  // an Infinite staleTime -- see Query.isStale(), which returns true whenever
  // state.isInvalidated is set, independent of staleTime.
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false, staleTime: Infinity },
    },
  });

  let serverMeet = makeMeet({ id: 4, name: "Spring Open", location: "Cape Town" });
  let meetCalls = 0;
  let standingsCalls = 0;
  server.use(
    http.get(api("/meets/4"), () => {
      meetCalls += 1;
      return HttpResponse.json(serverMeet);
    }),
    http.get(api("/districts/"), () => HttpResponse.json([])),
    http.get(api("/meets/4/standings"), () => {
      standingsCalls += 1;
      return HttpResponse.json({
        meet_id: 4,
        provisional: true,
        apparatus: "hoop",
        level: null,
        age_group: null,
        rankings: [],
      });
    }),
    http.get(api("/meets/4/all-around"), () =>
      HttpResponse.json({ meet_id: 4, provisional: true, level: null, age_group: null, rankings: [] }),
    ),
  );

  // Phase 1: visit the meet detail page once -- MeetShell caches ["meet", "4"] and
  // the standings tab caches ["standings", 4, ...].
  const firstVisit = renderAppWithClient("/meets/4/standings", queryClient);
  await screen.findByText("Spring Open");
  expect(meetCalls).toBe(1);
  expect(standingsCalls).toBe(1);
  firstVisit.unmount();

  // Phase 2: from the list (a fresh mount, same client), rename the same meet.
  server.use(
    http.get(api("/meets/"), () => HttpResponse.json([serverMeet])),
    http.patch(api("/meets/4"), async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      serverMeet = { ...serverMeet, ...body };
      return HttpResponse.json(serverMeet);
    }),
  );
  const listVisit = renderAppWithClient("/", queryClient);
  await userEvent.click(await screen.findByRole("button", { name: "Edit Spring Open" }));
  const dialog = within(screen.getByRole("dialog"));
  await userEvent.clear(dialog.getByLabelText("Name"));
  await userEvent.type(dialog.getByLabelText("Name"), "Spring Classic");
  await userEvent.click(dialog.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(serverMeet.name).toBe("Spring Classic"));
  listVisit.unmount();

  // Phase 3: revisit the detail page with the SAME client. Both the meet detail and
  // standings queries are cached and (under staleTime: Infinity) not naturally
  // stale -- only the invalidation from the list's save mutation forces a refetch.
  renderAppWithClient("/meets/4/standings", queryClient);
  await waitFor(() => expect(meetCalls).toBe(2));
  await waitFor(() => expect(standingsCalls).toBe(2));
  expect(await screen.findByText("Spring Classic")).toBeInTheDocument();
});

test("deleting a meet from the list drops its cached detail entry", async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });

  const meet = makeMeet({ id: 4, name: "Spring Open" });
  server.use(
    http.get(api("/meets/4"), () => HttpResponse.json(meet)),
    http.get(api("/districts/"), () => HttpResponse.json([])),
    http.get(api("/meets/4/standings"), () =>
      HttpResponse.json({
        meet_id: 4,
        provisional: true,
        apparatus: "hoop",
        level: null,
        age_group: null,
        rankings: [],
      }),
    ),
    http.get(api("/meets/4/all-around"), () =>
      HttpResponse.json({ meet_id: 4, provisional: true, level: null, age_group: null, rankings: [] }),
    ),
  );

  // Visit the detail page once so ["meet", "4"] is actually cached (the scenario
  // the bug describes: a stale detail entry left behind after the row is gone).
  const firstVisit = renderAppWithClient("/meets/4/standings", queryClient);
  await screen.findByText("Spring Open");
  expect(queryClient.getQueryData(["meet", "4"])).toBeDefined();
  firstVisit.unmount();

  server.use(http.get(api("/meets/"), () => HttpResponse.json([meet])));
  let deleteCalled = false;
  server.use(
    http.delete(api("/meets/4"), () => {
      deleteCalled = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderAppWithClient("/", queryClient);
  await userEvent.click(await screen.findByRole("button", { name: "Delete Spring Open" }));
  await waitFor(() => expect(deleteCalled).toBe(true));
  confirmSpy.mockRestore();

  // The cache entry must be gone outright, not merely marked stale -- the meet no
  // longer exists server-side, so there is nothing left to refetch against.
  expect(queryClient.getQueryData(["meet", "4"])).toBeUndefined();
});
