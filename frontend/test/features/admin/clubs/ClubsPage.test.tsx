import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeClub, makeDistrict } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

function mockBase(clubs: unknown[] = []) {
  server.use(
    http.get(api("/clubs/"), () => HttpResponse.json(clubs)),
    http.get(api("/districts/"), () =>
      HttpResponse.json([makeDistrict({ id: 1, name: "Western Cape" })]),
    ),
  );
}

test("lists clubs with their district name", async () => {
  mockBase([makeClub({ id: 5, name: "Star Gymnastics", abbreviation: "STAR", district_id: 1 })]);
  renderApp("/admin/clubs");
  expect(await screen.findByText("Star Gymnastics")).toBeInTheDocument();
  // Scoped to the table: "Western Cape" also appears as a district-filter
  // <option>, which is an equally valid getByText match outside the table.
  expect(
    within(screen.getByRole("table")).getByText("Western Cape"),
  ).toBeInTheDocument();
});

test("creates a club", async () => {
  mockBase();
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/clubs/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeClub(), { status: 201 });
    }),
  );
  renderApp("/admin/clubs");
  await userEvent.click(await screen.findByRole("button", { name: "New club" }));
  // "Western Cape" also appears as a district-filter <option> outside the
  // dialog, so scope the wait to the form's own District <select>.
  await within(screen.getByLabelText("District")).findByText("Western Cape");
  await userEvent.type(screen.getByLabelText("Name"), "Acro Academy");
  await userEvent.type(screen.getByLabelText("Abbreviation"), "ACRO");
  await userEvent.selectOptions(screen.getByLabelText("District"), "1");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({ name: "Acro Academy", abbreviation: "ACRO", district_id: 1 }),
  );
});

test("requires a district", async () => {
  mockBase();
  let called = false;
  server.use(
    http.post(api("/clubs/"), () => {
      called = true;
      return HttpResponse.json(makeClub(), { status: 201 });
    }),
  );
  renderApp("/admin/clubs");
  await userEvent.click(await screen.findByRole("button", { name: "New club" }));
  // "Western Cape" also appears as a district-filter <option> outside the
  // dialog, so scope the wait to the form's own District <select>.
  await within(screen.getByLabelText("District")).findByText("Western Cape");
  await userEvent.type(screen.getByLabelText("Name"), "Acro Academy");
  await userEvent.type(screen.getByLabelText("Abbreviation"), "ACRO");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Pick a district")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("edits a club, sending only the changed field", async () => {
  mockBase([makeClub({ id: 5, name: "Star Gymnastics", abbreviation: "STAR", district_id: 1 })]);
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/clubs/:clubId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeClub({ id: 5 }));
    }),
  );
  renderApp("/admin/clubs");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Star Gymnastics" }));
  const abbr = screen.getByLabelText("Abbreviation");
  await userEvent.clear(abbr);
  await userEvent.type(abbr, "STARS");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ abbreviation: "STARS" }));
});

test("district cannot be edited after club creation", async () => {
  mockBase([makeClub({ id: 5, name: "Star Gymnastics", abbreviation: "STAR", district_id: 1 })]);
  renderApp("/admin/clubs");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Star Gymnastics" }));
  await within(screen.getByLabelText("District")).findByText("Western Cape");
  const districtSelect = screen.getByLabelText("District") as HTMLSelectElement;
  expect(districtSelect.disabled).toBe(true);
});

test("surfaces a 409 when a club still has dependents", async () => {
  mockBase([makeClub({ id: 5, name: "Star Gymnastics", district_id: 1 })]);
  server.use(
    http.delete(api("/clubs/:clubId"), () =>
      HttpResponse.json({ detail: "Cannot delete club with existing gymnasts" }, { status: 409 }),
    ),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/clubs");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Star Gymnastics" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("existing gymnasts");
  confirmSpy.mockRestore();
});

test("a delete error is cleared by a later successful save", async () => {
  mockBase([makeClub({ id: 5, name: "Star Gymnastics", abbreviation: "STAR", district_id: 1 })]);
  server.use(
    http.delete(api("/clubs/:clubId"), () =>
      HttpResponse.json({ detail: "Cannot delete club with existing gymnasts" }, { status: 409 }),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/clubs/:clubId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeClub({ id: 5, name: "Star Gymnastics" }));
    }),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/clubs");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Star Gymnastics" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("existing gymnasts");

  await userEvent.click(screen.getByRole("button", { name: "Edit Star Gymnastics" }));
  const abbr = screen.getByLabelText("Abbreviation");
  await userEvent.clear(abbr);
  await userEvent.type(abbr, "STARS");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ abbreviation: "STARS" }));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  confirmSpy.mockRestore();
});

test("the district filter refetches scoped to that district", async () => {
  mockBase([makeClub({ id: 5, name: "Star Gymnastics", abbreviation: "STAR", district_id: 1 })]);
  const requested: (string | null)[] = [];
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([
        makeDistrict({ id: 1, name: "Western Cape" }),
        makeDistrict({ id: 2, name: "Gauteng" }),
      ]),
    ),
    http.get(api("/clubs/"), ({ request }) => {
      requested.push(new URL(request.url).searchParams.get("district_id"));
      return HttpResponse.json([]);
    }),
  );
  renderApp("/admin/clubs");
  // Wait for the districts list to actually populate the <select> before
  // selecting — the label itself renders synchronously, before the async
  // districts fetch resolves.
  await screen.findByText("Gauteng");
  await userEvent.selectOptions(screen.getByLabelText("District filter"), "2");
  await screen.findByText("No clubs yet.");
  expect(requested).toContain("2");
});

test("typing in the search box does not trigger a network request", async () => {
  mockBase([makeClub({ id: 5, name: "Star Gymnastics", abbreviation: "STAR", district_id: 1 })]);
  let requestCount = 0;
  server.use(
    http.get(api("/clubs/"), () => {
      requestCount += 1;
      return HttpResponse.json([
        makeClub({ id: 5, name: "Star Gymnastics", abbreviation: "STAR", district_id: 1 }),
      ]);
    }),
  );
  renderApp("/admin/clubs");
  await screen.findByText("Star Gymnastics");
  const countAfterLoad = requestCount;
  await userEvent.type(screen.getByLabelText("Search"), "star");
  expect(requestCount).toBe(countAfterLoad);
});

test("surfaces a failure to load districts", async () => {
  server.use(
    http.get(api("/clubs/"), () => HttpResponse.json([])),
    http.get(api("/districts/"), () =>
      HttpResponse.json({ detail: "districts unavailable" }, { status: 500 }),
    ),
  );
  renderApp("/admin/clubs");
  expect(await screen.findByRole("alert")).toHaveTextContent("districts unavailable");
});
