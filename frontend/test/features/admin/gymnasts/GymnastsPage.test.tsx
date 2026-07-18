import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeClub, makeGymnast } from "../../../fixtures";
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
  // dob and country are filled in so the club cell is the only em dash on the row.
  mockBase([
    makeGymnast({
      id: 11,
      first_name: "Mia",
      last_name: "Nel",
      club_id: null,
      date_of_birth: "2012-08-19",
      country_code: "RSA",
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
