import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeClub, makeGroup } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

function mockBase(groups: unknown[] = []) {
  server.use(
    http.get(api("/groups/"), () => HttpResponse.json(groups)),
    http.get(api("/clubs/"), () =>
      HttpResponse.json([makeClub({ id: 1, name: "Star Gymnastics" })]),
    ),
  );
}

test("lists groups with their club", async () => {
  mockBase([makeGroup({ id: 3, name: "Zvezda RG", club_id: 1 })]);
  renderApp("/admin/groups");
  expect(await screen.findByText("Zvezda RG")).toBeInTheDocument();
  // Scoped to the table: "Star Gymnastics" also appears as a club-filter
  // <option> and in the form's Club <select>, which are equally valid
  // getByText matches outside the table.
  expect(within(screen.getByRole("table")).getByText("Star Gymnastics")).toBeInTheDocument();
});

test("creates a group", async () => {
  mockBase();
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/groups/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGroup(), { status: 201 });
    }),
  );
  renderApp("/admin/groups");
  await userEvent.click(await screen.findByRole("button", { name: "New group" }));
  await within(screen.getByLabelText("Club")).findByText("Star Gymnastics");
  await userEvent.type(screen.getByLabelText("Name"), "Junior Ensemble");
  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(posted).toEqual({ name: "Junior Ensemble", club_id: 1 }));
});

test("requires a name of at least 2 characters", async () => {
  mockBase();
  let called = false;
  server.use(
    http.post(api("/groups/"), () => {
      called = true;
      return HttpResponse.json(makeGroup(), { status: 201 });
    }),
  );
  renderApp("/admin/groups");
  await userEvent.click(await screen.findByRole("button", { name: "New group" }));
  await within(screen.getByLabelText("Club")).findByText("Star Gymnastics");
  await userEvent.type(screen.getByLabelText("Name"), "J");
  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("At least 2 characters")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("edits a group name", async () => {
  mockBase([makeGroup({ id: 3, name: "Zvezda RG", club_id: 1 })]);
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/groups/:groupId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGroup({ id: 3 }));
    }),
  );
  renderApp("/admin/groups");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Zvezda RG" }));
  const name = screen.getByLabelText("Name");
  await userEvent.clear(name);
  await userEvent.type(name, "Zvezda Seniors");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ name: "Zvezda Seniors" }));
});

test("club cannot be edited after group creation", async () => {
  mockBase([makeGroup({ id: 3, name: "Zvezda RG", club_id: 1 })]);
  renderApp("/admin/groups");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Zvezda RG" }));
  await within(screen.getByLabelText("Club")).findByText("Star Gymnastics");
  const clubSelect = screen.getByLabelText("Club") as HTMLSelectElement;
  expect(clubSelect.disabled).toBe(true);
});

test("surfaces a 409 when the group still has members", async () => {
  mockBase([makeGroup({ id: 3, name: "Zvezda RG", club_id: 1 })]);
  server.use(
    http.delete(api("/groups/:groupId"), () =>
      HttpResponse.json({ detail: "Cannot delete group with existing members" }, { status: 409 }),
    ),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/groups");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Zvezda RG" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("existing members");
  confirmSpy.mockRestore();
});

test("a delete error is cleared by a later successful save", async () => {
  mockBase([makeGroup({ id: 3, name: "Zvezda RG", club_id: 1 })]);
  server.use(
    http.delete(api("/groups/:groupId"), () =>
      HttpResponse.json({ detail: "Cannot delete group with existing members" }, { status: 409 }),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/groups/:groupId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGroup({ id: 3, name: "Zvezda Seniors" }));
    }),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/groups");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Zvezda RG" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("existing members");

  await userEvent.click(screen.getByRole("button", { name: "Edit Zvezda RG" }));
  const name = screen.getByLabelText("Name");
  await userEvent.clear(name);
  await userEvent.type(name, "Zvezda Seniors");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ name: "Zvezda Seniors" }));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  confirmSpy.mockRestore();
});

test("the club filter refetches scoped to that club", async () => {
  mockBase([makeGroup({ id: 3, name: "Zvezda RG", club_id: 1 })]);
  const requested: (string | null)[] = [];
  server.use(
    http.get(api("/clubs/"), () =>
      HttpResponse.json([
        makeClub({ id: 1, name: "Star Gymnastics" }),
        makeClub({ id: 2, name: "Acro Academy" }),
      ]),
    ),
    http.get(api("/groups/"), ({ request }) => {
      requested.push(new URL(request.url).searchParams.get("club_id"));
      return HttpResponse.json([]);
    }),
  );
  renderApp("/admin/groups");
  // Wait for the clubs list to actually populate the <select> before
  // selecting — the label itself renders synchronously, before the async
  // clubs fetch resolves.
  await screen.findByText("Acro Academy");
  await userEvent.selectOptions(screen.getByLabelText("Club filter"), "2");
  await screen.findByText("No groups yet.");
  expect(requested).toContain("2");
});

test("typing in the search box does not trigger a network request", async () => {
  mockBase([makeGroup({ id: 3, name: "Zvezda RG", club_id: 1 })]);
  let requestCount = 0;
  server.use(
    http.get(api("/groups/"), () => {
      requestCount += 1;
      return HttpResponse.json([makeGroup({ id: 3, name: "Zvezda RG", club_id: 1 })]);
    }),
  );
  renderApp("/admin/groups");
  await screen.findByText("Zvezda RG");
  const countAfterLoad = requestCount;
  await userEvent.type(screen.getByLabelText("Search"), "zvezda");
  expect(requestCount).toBe(countAfterLoad);
});

test("surfaces a failure to load clubs", async () => {
  server.use(
    http.get(api("/groups/"), () => HttpResponse.json([])),
    http.get(api("/clubs/"), () =>
      HttpResponse.json({ detail: "clubs unavailable" }, { status: 500 }),
    ),
  );
  renderApp("/admin/groups");
  expect(await screen.findByRole("alert")).toHaveTextContent("clubs unavailable");
});
