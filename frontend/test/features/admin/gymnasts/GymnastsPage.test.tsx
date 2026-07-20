import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeClub, makeGroup, makeGymnast } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

function mockBase(gymnasts: unknown[] = []) {
  server.use(
    http.get(api("/gymnasts/"), () => HttpResponse.json(gymnasts)),
    http.get(api("/clubs/"), () =>
      HttpResponse.json([
        makeClub({ id: 1, name: "Star Gymnastics" }),
        makeClub({ id: 2, name: "Acro Academy" }),
      ]),
    ),
    http.get(api("/groups/"), () => HttpResponse.json([])),
  );
}

test("lists gymnasts with their club name", async () => {
  mockBase([
    makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", club_id: 1 }),
  ]);
  renderApp("/admin/gymnasts");
  expect(await screen.findByText("Anna Botha")).toBeInTheDocument();
  // Scoped to the table: "Star Gymnastics" also appears as a club-filter
  // <option>, which is an equally valid getByText match outside the table.
  expect(
    within(screen.getByRole("table")).getByText("Star Gymnastics"),
  ).toBeInTheDocument();
});

test("shows an em dash for a gymnast with no club", async () => {
  // dob, country and GSA number are filled in so the club cell is the only em dash.
  mockBase([
    makeGymnast({
      id: 11,
      first_name: "Mia",
      last_name: "Nel",
      club_id: null,
      date_of_birth: "2012-08-19",
      country_code: "RSA",
      gsa_number: "GSA-311",
    }),
  ]);
  renderApp("/admin/gymnasts");
  expect(await screen.findByText("Mia Nel")).toBeInTheDocument();
  expect(screen.getByText("—")).toBeInTheDocument();
});

test("search filters rows by name, client-side", async () => {
  mockBase([
    makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", club_id: 1 }),
    makeGymnast({ id: 11, first_name: "Mia", last_name: "Nel", club_id: 2 }),
  ]);
  renderApp("/admin/gymnasts");
  await screen.findByText("Anna Botha");
  await userEvent.type(screen.getByLabelText("Search"), "nel");
  expect(screen.queryByText("Anna Botha")).toBeNull();
  expect(screen.getByText("Mia Nel")).toBeInTheDocument();
});

test("the club filter refetches scoped to that club", async () => {
  mockBase([makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", club_id: 1 })]);
  const requested: (string | null)[] = [];
  server.use(
    http.get(api("/gymnasts/"), ({ request }) => {
      requested.push(new URL(request.url).searchParams.get("club_id"));
      return HttpResponse.json([]);
    }),
  );
  renderApp("/admin/gymnasts");
  // Wait for the clubs list to actually populate the <select> before
  // selecting — the label itself renders synchronously, before the async
  // clubs fetch resolves.
  await screen.findByText("Acro Academy");
  await userEvent.selectOptions(screen.getByLabelText("Club filter"), "2");
  await screen.findByText("No gymnasts yet.");
  expect(requested).toContain("2");
});

test("surface clubs fetch error when gymnasts succeeds", async () => {
  server.use(
    http.get(api("/gymnasts/"), () =>
      HttpResponse.json([
        makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", club_id: 1 }),
      ]),
    ),
    http.get(api("/clubs/"), () =>
      HttpResponse.json({ detail: "Clubs endpoint failed" }, { status: 500 }),
    ),
    http.get(api("/groups/"), () => HttpResponse.json([])),
  );
  renderApp("/admin/gymnasts");
  expect(await screen.findByText("Clubs endpoint failed")).toBeInTheDocument();
});

test("creates a gymnast, sending nulls for the fields left blank", async () => {
  mockBase();
  server.use(
    http.get(api("/groups/"), () =>
      HttpResponse.json([makeGroup({ id: 3, name: "Zvezda RG" })]),
    ),
  );
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/gymnasts/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast(), { status: 201 });
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));
  await userEvent.type(screen.getByLabelText("First name"), "Zoe");
  await userEvent.type(screen.getByLabelText("Last name"), "Kruger");
  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({
      first_name: "Zoe",
      last_name: "Kruger",
      club_id: 1,
      group_id: null,
      date_of_birth: null,
      country_code: null,
      ethnicity: null,
      gsa_number: null,
    }),
  );
});

test("sends the optional date and country when filled in", async () => {
  mockBase();
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/gymnasts/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast(), { status: 201 });
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));
  await userEvent.type(screen.getByLabelText("First name"), "Zoe");
  await userEvent.type(screen.getByLabelText("Last name"), "Kruger");
  await userEvent.type(screen.getByLabelText("Date of birth"), "2011-04-02");
  await userEvent.type(screen.getByLabelText("Country code"), "RSA");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toMatchObject({ date_of_birth: "2011-04-02", country_code: "RSA" }),
  );
});

test("rejects an over-long country code before sending", async () => {
  mockBase();
  let called = false;
  server.use(
    http.post(api("/gymnasts/"), () => {
      called = true;
      return HttpResponse.json(makeGymnast(), { status: 201 });
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));
  await userEvent.type(screen.getByLabelText("First name"), "Zoe");
  await userEvent.type(screen.getByLabelText("Last name"), "Kruger");
  await userEvent.type(screen.getByLabelText("Country code"), "RSAX");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("At most 3 characters")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("surfaces a groups fetch error when gymnasts and clubs succeed", async () => {
  server.use(
    http.get(api("/gymnasts/"), () =>
      HttpResponse.json([
        makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", club_id: 1 }),
      ]),
    ),
    http.get(api("/clubs/"), () => HttpResponse.json([])),
    http.get(api("/groups/"), () =>
      HttpResponse.json({ detail: "Groups endpoint failed" }, { status: 500 }),
    ),
  );
  renderApp("/admin/gymnasts");
  expect(await screen.findByText("Groups endpoint failed")).toBeInTheDocument();
});

test("clears a stale form error once a retry succeeds", async () => {
  mockBase();
  let attempts = 0;
  server.use(
    http.post(api("/gymnasts/"), async () => {
      attempts += 1;
      if (attempts === 1) {
        return HttpResponse.json({ detail: "club_id: FK not found" }, { status: 404 });
      }
      return HttpResponse.json(makeGymnast(), { status: 201 });
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));
  await userEvent.type(screen.getByLabelText("First name"), "Zoe");
  await userEvent.type(screen.getByLabelText("Last name"), "Kruger");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("club_id: FK not found")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  // A successful save closes the dialog, which takes the stale error with it.
  await waitFor(() => expect(screen.queryByText("club_id: FK not found")).toBeNull());
  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));
  expect(screen.queryByText("club_id: FK not found")).toBeNull();
});

test("edit sends only the changed field and leaves the untouched group alone", async () => {
  mockBase([
    makeGymnast({
      id: 10,
      first_name: "Anna",
      last_name: "Botha",
      club_id: 1,
      group_id: 3,
      date_of_birth: "2011-04-02",
    }),
  ]);
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/gymnasts/:gymnastId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast({ id: 10 }));
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Anna Botha" }));
  const last = screen.getByLabelText("Last name");
  await userEvent.clear(last);
  await userEvent.type(last, "Botha-Smit");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ last_name: "Botha-Smit" }));
});

test("clearing the club sends an explicit null", async () => {
  mockBase([
    makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", club_id: 1 }),
  ]);
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/gymnasts/:gymnastId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast({ id: 10 }));
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Anna Botha" }));
  await userEvent.selectOptions(screen.getByLabelText("Club"), "");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ club_id: null }));
});

test("deletes a gymnast after confirmation and surfaces a 409", async () => {
  mockBase([
    makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", club_id: 1 }),
  ]);
  server.use(
    http.delete(api("/gymnasts/:gymnastId"), () =>
      HttpResponse.json({ detail: "Cannot delete gymnast with entries" }, { status: 409 }),
    ),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Anna Botha" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("with entries");
  expect(confirmSpy.mock.calls[0][0]).toContain("Anna Botha");
  confirmSpy.mockRestore();
});

test("a later successful save clears a stale delete error", async () => {
  mockBase([
    makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", club_id: 1 }),
  ]);
  server.use(
    http.delete(api("/gymnasts/:gymnastId"), () =>
      HttpResponse.json({ detail: "Cannot delete gymnast with entries" }, { status: 409 }),
    ),
    http.patch(api("/gymnasts/:gymnastId"), () =>
      HttpResponse.json(makeGymnast({ id: 10, first_name: "Anna", last_name: "Ndlovu" })),
    ),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Anna Botha" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("with entries");
  confirmSpy.mockRestore();

  await userEvent.click(screen.getByRole("button", { name: "Edit Anna Botha" }));
  const last = screen.getByLabelText("Last name");
  await userEvent.clear(last);
  await userEvent.type(last, "Ndlovu");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
});

test("offers only groups belonging to the selected club", async () => {
  server.use(http.get(api("/gymnasts/"), () => HttpResponse.json([])));
  server.use(
    http.get(api("/clubs/"), () =>
      HttpResponse.json([makeClub({ id: 1, name: "Cape RG" }), makeClub({ id: 2, name: "Durban RG" })]),
    ),
  );
  server.use(
    http.get(api("/groups/"), () =>
      HttpResponse.json([
        makeGroup({ id: 10, club_id: 1, name: "Cape Juniors" }),
        makeGroup({ id: 20, club_id: 2, name: "Durban Seniors" }),
      ]),
    ),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));

  const group = screen.getByLabelText("Group");
  expect(group).toBeDisabled();

  // Scoped to the dialog: "Cape RG" also appears as a page-level club-filter
  // <option>, which is an equally valid (but wrong) getByText match otherwise.
  const dialog = screen.getByRole("dialog");
  await waitFor(() => expect(within(dialog).getByText("Cape RG")).toBeInTheDocument());
  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");

  expect(group).toBeEnabled();
  expect(within(group).getByText("Cape Juniors")).toBeInTheDocument();
  expect(within(group).queryByText("Durban Seniors")).not.toBeInTheDocument();
});

test("clears the group when the club changes", async () => {
  server.use(http.get(api("/gymnasts/"), () => HttpResponse.json([])));
  server.use(
    http.get(api("/clubs/"), () =>
      HttpResponse.json([makeClub({ id: 1, name: "Cape RG" }), makeClub({ id: 2, name: "Durban RG" })]),
    ),
  );
  server.use(
    http.get(api("/groups/"), () =>
      HttpResponse.json([
        makeGroup({ id: 10, club_id: 1, name: "Cape Juniors" }),
        makeGroup({ id: 20, club_id: 2, name: "Durban Seniors" }),
      ]),
    ),
  );
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/gymnasts/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast(), { status: 201 });
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));
  // Scoped to the dialog: "Cape RG" also appears as a page-level club-filter
  // <option>, which is an equally valid (but wrong) getByText match otherwise.
  await waitFor(() =>
    expect(within(screen.getByRole("dialog")).getByText("Cape RG")).toBeInTheDocument(),
  );

  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");
  await userEvent.selectOptions(screen.getByLabelText("Group"), "10");
  await userEvent.selectOptions(screen.getByLabelText("Club"), "2");

  expect((screen.getByLabelText("Group") as HTMLSelectElement).value).toBe("");

  await userEvent.type(screen.getByLabelText("First name"), "Ana");
  await userEvent.type(screen.getByLabelText("Last name"), "Meyer");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({
      first_name: "Ana",
      last_name: "Meyer",
      club_id: 2,
      group_id: null,
      date_of_birth: null,
      country_code: null,
      ethnicity: null,
      gsa_number: null,
    }),
  );
});

test("edit: changing the club clears the group in the PATCH body", async () => {
  // Group 10 belongs to club 1, so it is NOT an orphan for this gymnast — this
  // isolates the shouldDirty behaviour from the separate orphan-preservation path.
  mockBase([
    makeGymnast({
      id: 10,
      first_name: "Anna",
      last_name: "Botha",
      club_id: 1,
      group_id: 10,
    }),
  ]);
  server.use(
    http.get(api("/clubs/"), () =>
      HttpResponse.json([makeClub({ id: 1, name: "Cape RG" }), makeClub({ id: 2, name: "Durban RG" })]),
    ),
  );
  server.use(
    http.get(api("/groups/"), () =>
      HttpResponse.json([
        makeGroup({ id: 10, club_id: 1, name: "Cape Juniors" }),
        makeGroup({ id: 20, club_id: 2, name: "Durban Seniors" }),
      ]),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/gymnasts/:gymnastId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast({ id: 10 }));
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Anna Botha" }));

  const group = screen.getByLabelText("Group") as HTMLSelectElement;
  await waitFor(() => expect(group.value).toBe("10"));

  await userEvent.selectOptions(screen.getByLabelText("Club"), "2");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => expect(patched).toEqual({ club_id: 2, group_id: null }));
});

test("keeps an orphaned group in the options and does not drop it on an unrelated save", async () => {
  // Gymnast 5 is in club 1 but assigned group 20, which belongs to club 2.
  // Filtering must not blank the select and silently unassign the group.
  server.use(
    http.get(api("/gymnasts/"), () =>
      HttpResponse.json([
        makeGymnast({ id: 5, club_id: 1, group_id: 20, first_name: "Ana", last_name: "Meyer" }),
      ]),
    ),
  );
  server.use(http.get(api("/clubs/"), () => HttpResponse.json([makeClub({ id: 1, name: "Cape RG" })])));
  server.use(
    http.get(api("/groups/"), () =>
      HttpResponse.json([
        makeGroup({ id: 10, club_id: 1, name: "Cape Juniors" }),
        makeGroup({ id: 20, club_id: 2, name: "Durban Seniors" }),
      ]),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/gymnasts/5"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast({ id: 5 }));
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Ana Meyer" }));

  const group = screen.getByLabelText("Group") as HTMLSelectElement;
  await waitFor(() => expect(group.value).toBe("20"));
  // Must be flagged as belonging to another club, not just present by name.
  expect(within(group).getByText("Durban Seniors (other club)")).toBeInTheDocument();

  const first = screen.getByLabelText("First name");
  await userEvent.clear(first);
  await userEvent.type(first, "Anna");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => expect(patched).toEqual({ first_name: "Anna" }));
});

test("edit: does not resurrect the original group as a ghost option after the club is changed", async () => {
  // Group 10 genuinely belongs to club 1, the gymnast's originally-loaded club -- it
  // is NOT an orphan. Once the user actively changes Club away from club 1, group 10
  // must not reappear as a flagged " (other club)" ghost: that flag exists only to
  // preserve the as-loaded pairing, and the user has just replaced it.
  mockBase([
    makeGymnast({
      id: 10,
      first_name: "Anna",
      last_name: "Botha",
      club_id: 1,
      group_id: 10,
    }),
  ]);
  server.use(
    http.get(api("/clubs/"), () =>
      HttpResponse.json([makeClub({ id: 1, name: "Cape RG" }), makeClub({ id: 2, name: "Durban RG" })]),
    ),
  );
  server.use(
    http.get(api("/groups/"), () =>
      HttpResponse.json([
        makeGroup({ id: 10, club_id: 1, name: "Cape Juniors" }),
        makeGroup({ id: 20, club_id: 2, name: "Durban Seniors" }),
      ]),
    ),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Anna Botha" }));

  const group = screen.getByLabelText("Group") as HTMLSelectElement;
  await waitFor(() => expect(group.value).toBe("10"));
  expect(within(group).getByText("Cape Juniors")).toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText("Club"), "2");

  expect(within(group).getByText("Durban Seniors")).toBeInTheDocument();
  expect(within(group).queryByText("Cape Juniors")).not.toBeInTheDocument();
  expect(within(group).queryByText(/\(other club\)/)).not.toBeInTheDocument();
});

test("edit: does not resurrect the ghost after a club round-trip back to the original club", async () => {
  // Gymnast 5 is a true orphan: club 1, group 20, where group 20 belongs to
  // club 2. The ghost must show on load, but once the user changes the club
  // away and then back to club 1 (an ordinary "go back" correction), group_id
  // has been cleared and no longer matches the as-loaded pairing -- the ghost
  // must not reappear, or the user could select it and reconstruct the exact
  // invalid club/group pair this filter exists to prevent.
  server.use(
    http.get(api("/gymnasts/"), () =>
      HttpResponse.json([
        makeGymnast({ id: 5, club_id: 1, group_id: 20, first_name: "Ana", last_name: "Meyer" }),
      ]),
    ),
  );
  server.use(
    http.get(api("/clubs/"), () =>
      HttpResponse.json([makeClub({ id: 1, name: "Cape RG" }), makeClub({ id: 2, name: "Durban RG" })]),
    ),
  );
  server.use(
    http.get(api("/groups/"), () =>
      HttpResponse.json([
        makeGroup({ id: 10, club_id: 1, name: "Cape Juniors" }),
        makeGroup({ id: 20, club_id: 2, name: "Durban Seniors" }),
      ]),
    ),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Ana Meyer" }));

  const group = screen.getByLabelText("Group") as HTMLSelectElement;
  await waitFor(() => expect(group.value).toBe("20"));
  expect(within(group).getByText("Durban Seniors (other club)")).toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText("Club"), "2");
  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");

  expect(within(group).queryByText(/\(other club\)/)).not.toBeInTheDocument();
  expect(screen.queryByText("Durban Seniors (other club)")).not.toBeInTheDocument();
});

test("submits ethnicity and GSA number when creating a gymnast", async () => {
  mockBase([]);
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/gymnasts/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast({ id: 99 }), { status: 201 });
    }),
  );
  renderApp("/admin/gymnasts");

  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));
  await userEvent.type(screen.getByLabelText("First name"), "Dina");
  await userEvent.type(screen.getByLabelText("Last name"), "Averina");
  await userEvent.selectOptions(screen.getByLabelText("Ethnicity"), "indian");
  await userEvent.type(screen.getByLabelText("GSA number"), "GSA-1001");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() =>
    expect(posted).toMatchObject({ ethnicity: "indian", gsa_number: "GSA-1001" }),
  );
});

test("ethnicity defaults to a blank not-set option", async () => {
  mockBase([]);
  renderApp("/admin/gymnasts");

  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));

  const select = screen.getByLabelText("Ethnicity") as HTMLSelectElement;
  expect(select.value).toBe("");
  // 5 enum values + the blank "not set" option
  expect(within(select).getAllByRole("option")).toHaveLength(6);
});

test("shows the GSA number column, with an em dash when unset", async () => {
  mockBase([
    makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", gsa_number: "GSA-500" }),
  ]);
  renderApp("/admin/gymnasts");

  expect(
    await screen.findByRole("columnheader", { name: "GSA number" }),
  ).toBeInTheDocument();
  expect(screen.getByText("GSA-500")).toBeInTheDocument();
});

test("does not show ethnicity in the roster table", async () => {
  mockBase([makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha" })]);
  renderApp("/admin/gymnasts");

  await screen.findByRole("columnheader", { name: "GSA number" });
  expect(
    screen.queryByRole("columnheader", { name: /ethnicity/i }),
  ).not.toBeInTheDocument();
});

test("edit prefills ethnicity and GSA number from the existing gymnast", async () => {
  mockBase([
    makeGymnast({
      id: 10,
      first_name: "Anna",
      last_name: "Botha",
      ethnicity: "indian",
      gsa_number: "GSA-777",
    }),
  ]);
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Anna Botha" }));
  expect((screen.getByLabelText("Ethnicity") as HTMLSelectElement).value).toBe("indian");
  expect((screen.getByLabelText("GSA number") as HTMLInputElement).value).toBe("GSA-777");
});

test("edit: clearing ethnicity and GSA number sends explicit nulls", async () => {
  mockBase([
    makeGymnast({
      id: 10,
      first_name: "Anna",
      last_name: "Botha",
      ethnicity: "indian",
      gsa_number: "GSA-777",
    }),
  ]);
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/gymnasts/:gymnastId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast({ id: 10 }));
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Anna Botha" }));
  await userEvent.selectOptions(screen.getByLabelText("Ethnicity"), "");
  await userEvent.clear(screen.getByLabelText("GSA number"));
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ ethnicity: null, gsa_number: null }));
});

test("edit: changing only ethnicity sends only that field in the PATCH body", async () => {
  mockBase([
    makeGymnast({
      id: 10,
      first_name: "Anna",
      last_name: "Botha",
      ethnicity: "indian",
      gsa_number: "GSA-777",
    }),
  ]);
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/gymnasts/:gymnastId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast({ id: 10 }));
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Anna Botha" }));
  await userEvent.selectOptions(screen.getByLabelText("Ethnicity"), "black");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ ethnicity: "black" }));
});
