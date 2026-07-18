import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeClub, makeCoach } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

function mockBase(coaches: unknown[] = []) {
  server.use(
    http.get(api("/coaches/"), () => HttpResponse.json(coaches)),
    http.get(api("/clubs/"), () =>
      HttpResponse.json([makeClub({ id: 1, name: "Star Gymnastics" })]),
    ),
  );
}

test("lists coaches with club and head-coach status", async () => {
  mockBase([
    makeCoach({ id: 7, first_name: "Thabo", last_name: "Mokoena", club_id: 1, is_head_coach: true }),
  ]);
  renderApp("/admin/coaches");
  expect(await screen.findByText("Thabo Mokoena")).toBeInTheDocument();
  // Scoped to the table: "Star Gymnastics" also appears as a club-filter
  // <option> and in the form's Club <select>, which are equally valid
  // getByText matches outside the table.
  expect(within(screen.getByRole("table")).getByText("Star Gymnastics")).toBeInTheDocument();
  expect(within(screen.getByRole("table")).getByText("Head coach")).toBeInTheDocument();
});

test("creates a coach with the head-coach flag", async () => {
  mockBase();
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/coaches/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeCoach(), { status: 201 });
    }),
  );
  renderApp("/admin/coaches");
  await userEvent.click(await screen.findByRole("button", { name: "New coach" }));
  // "Star Gymnastics" also appears as a club-filter <option> outside the
  // dialog, so scope the wait to the form's own Club <select>.
  await within(screen.getByLabelText("Club")).findByText("Star Gymnastics");
  await userEvent.type(screen.getByLabelText("First name"), "Thabo");
  await userEvent.type(screen.getByLabelText("Last name"), "Mokoena");
  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");
  await userEvent.click(screen.getByLabelText("Head coach"));
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({
      first_name: "Thabo",
      last_name: "Mokoena",
      club_id: 1,
      is_head_coach: true,
    }),
  );
});

test("requires first and last names of at least 2 characters", async () => {
  mockBase();
  let called = false;
  server.use(
    http.post(api("/coaches/"), () => {
      called = true;
      return HttpResponse.json(makeCoach(), { status: 201 });
    }),
  );
  renderApp("/admin/coaches");
  await userEvent.click(await screen.findByRole("button", { name: "New coach" }));
  await within(screen.getByLabelText("Club")).findByText("Star Gymnastics");
  await userEvent.type(screen.getByLabelText("First name"), "T");
  await userEvent.type(screen.getByLabelText("Last name"), "Mokoena");
  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("At least 2 characters")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("edits a coach, sending only the toggled flag", async () => {
  mockBase([
    makeCoach({ id: 7, first_name: "Thabo", last_name: "Mokoena", club_id: 1, is_head_coach: false }),
  ]);
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/coaches/:coachId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeCoach({ id: 7 }));
    }),
  );
  renderApp("/admin/coaches");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Thabo Mokoena" }));
  await userEvent.click(screen.getByLabelText("Head coach"));
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ is_head_coach: true }));
});

test("club cannot be edited after coach creation", async () => {
  mockBase([
    makeCoach({ id: 7, first_name: "Thabo", last_name: "Mokoena", club_id: 1, is_head_coach: false }),
  ]);
  renderApp("/admin/coaches");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Thabo Mokoena" }));
  await within(screen.getByLabelText("Club")).findByText("Star Gymnastics");
  const clubSelect = screen.getByLabelText("Club") as HTMLSelectElement;
  expect(clubSelect.disabled).toBe(true);
});

test("surfaces a duplicate-identity 409", async () => {
  mockBase();
  server.use(
    http.post(api("/coaches/"), () =>
      HttpResponse.json({ detail: "Coach already exists in this club" }, { status: 409 }),
    ),
  );
  renderApp("/admin/coaches");
  await userEvent.click(await screen.findByRole("button", { name: "New coach" }));
  await within(screen.getByLabelText("Club")).findByText("Star Gymnastics");
  await userEvent.type(screen.getByLabelText("First name"), "Thabo");
  await userEvent.type(screen.getByLabelText("Last name"), "Mokoena");
  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("already exists");
});

test("surfaces a 409 when a coach delete is rejected", async () => {
  mockBase([makeCoach({ id: 7, first_name: "Thabo", last_name: "Mokoena", club_id: 1 })]);
  server.use(
    http.delete(api("/coaches/:coachId"), () =>
      HttpResponse.json({ detail: "Cannot delete coach with id 7" }, { status: 409 }),
    ),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/coaches");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Thabo Mokoena" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Cannot delete coach with id 7");
  confirmSpy.mockRestore();
});

test("a delete error is cleared by a later successful save", async () => {
  mockBase([
    makeCoach({ id: 7, first_name: "Thabo", last_name: "Mokoena", club_id: 1, is_head_coach: false }),
  ]);
  server.use(
    http.delete(api("/coaches/:coachId"), () =>
      HttpResponse.json({ detail: "Cannot delete coach with id 7" }, { status: 409 }),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/coaches/:coachId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeCoach({ id: 7, first_name: "Thabo", last_name: "Mokoena" }));
    }),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/coaches");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Thabo Mokoena" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Cannot delete coach with id 7");

  await userEvent.click(screen.getByRole("button", { name: "Edit Thabo Mokoena" }));
  await userEvent.click(screen.getByLabelText("Head coach"));
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ is_head_coach: true }));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  confirmSpy.mockRestore();
});

test("the club filter refetches scoped to that club", async () => {
  mockBase([makeCoach({ id: 7, first_name: "Thabo", last_name: "Mokoena", club_id: 1 })]);
  const requested: (string | null)[] = [];
  server.use(
    http.get(api("/clubs/"), () =>
      HttpResponse.json([
        makeClub({ id: 1, name: "Star Gymnastics" }),
        makeClub({ id: 2, name: "Acro Academy" }),
      ]),
    ),
    http.get(api("/coaches/"), ({ request }) => {
      requested.push(new URL(request.url).searchParams.get("club_id"));
      return HttpResponse.json([]);
    }),
  );
  renderApp("/admin/coaches");
  // Wait for the clubs list to actually populate the <select> before
  // selecting — the label itself renders synchronously, before the async
  // clubs fetch resolves.
  await screen.findByText("Acro Academy");
  await userEvent.selectOptions(screen.getByLabelText("Club filter"), "2");
  await screen.findByText("No coaches yet.");
  expect(requested).toContain("2");
});

test("search filters rows client-side", async () => {
  mockBase([
    makeCoach({ id: 7, first_name: "Thabo", last_name: "Mokoena", club_id: 1 }),
    makeCoach({ id: 8, first_name: "Lerato", last_name: "Dlamini", club_id: 1 }),
  ]);
  renderApp("/admin/coaches");
  await screen.findByText("Thabo Mokoena");
  const table = screen.getByRole("table");
  // "dlamini" only matches via the last-name half of the searchText accessor.
  await userEvent.type(screen.getByLabelText("Search"), "dlamini");
  expect(within(table).queryByText("Thabo Mokoena")).toBeNull();
  expect(within(table).getByText("Lerato Dlamini")).toBeInTheDocument();
});

test("typing in the search box does not trigger a network request", async () => {
  mockBase([makeCoach({ id: 7, first_name: "Thabo", last_name: "Mokoena", club_id: 1 })]);
  let requestCount = 0;
  server.use(
    http.get(api("/coaches/"), () => {
      requestCount += 1;
      return HttpResponse.json([
        makeCoach({ id: 7, first_name: "Thabo", last_name: "Mokoena", club_id: 1 }),
      ]);
    }),
  );
  renderApp("/admin/coaches");
  await screen.findByText("Thabo Mokoena");
  const countAfterLoad = requestCount;
  await userEvent.type(screen.getByLabelText("Search"), "thabo");
  expect(requestCount).toBe(countAfterLoad);
});

test("surfaces a failure to load clubs", async () => {
  server.use(
    http.get(api("/coaches/"), () => HttpResponse.json([])),
    http.get(api("/clubs/"), () =>
      HttpResponse.json({ detail: "clubs unavailable" }, { status: 500 }),
    ),
  );
  renderApp("/admin/coaches");
  expect(await screen.findByRole("alert")).toHaveTextContent("clubs unavailable");
});
