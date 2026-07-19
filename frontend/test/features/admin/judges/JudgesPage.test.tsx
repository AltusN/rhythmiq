import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeJudge } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

test("lists judges", async () => {
  server.use(
    http.get(api("/judges/"), () =>
      HttpResponse.json([
        makeJudge({ id: 1, first_name: "Naledi", last_name: "Dlamini", country_code: "RSA", brevet: "Cat I" }),
        makeJudge({ id: 2, first_name: "Elena", last_name: "Petrova", country_code: "BUL", brevet: null }),
      ]),
    ),
  );
  renderApp("/admin/judges");
  expect(await screen.findByText("Naledi")).toBeInTheDocument();
  // Scope to the table: country codes also appear as <option>s in the country filter.
  const table = within(screen.getByRole("table"));
  expect(table.getByText("Cat I")).toBeInTheDocument();
  expect(table.getByText("BUL")).toBeInTheDocument();
});

test("shows an empty message when there are no judges", async () => {
  server.use(http.get(api("/judges/"), () => HttpResponse.json([])));
  renderApp("/admin/judges");
  expect(await screen.findByText("No judges yet.")).toBeInTheDocument();
});

test("surfaces a list error", async () => {
  server.use(
    http.get(api("/judges/"), () =>
      HttpResponse.json({ detail: "Database unavailable" }, { status: 500 }),
    ),
  );
  renderApp("/admin/judges");
  expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable");
});

test("creates a judge, sending nulls for blank optional fields", async () => {
  server.use(http.get(api("/judges/"), () => HttpResponse.json([])));
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/judges/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeJudge(), { status: 201 });
    }),
  );
  renderApp("/admin/judges");
  await userEvent.click(await screen.findByRole("button", { name: "New judge" }));
  await userEvent.type(screen.getByLabelText("First name"), "Ana");
  await userEvent.type(screen.getByLabelText("Last name"), "Meyer");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({
      first_name: "Ana",
      last_name: "Meyer",
      country_code: null,
      brevet: null,
    }),
  );
});

test("does not uppercase the country code client-side", async () => {
  server.use(http.get(api("/judges/"), () => HttpResponse.json([])));
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/judges/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeJudge(), { status: 201 });
    }),
  );
  renderApp("/admin/judges");
  await userEvent.click(await screen.findByRole("button", { name: "New judge" }));
  await userEvent.type(screen.getByLabelText("First name"), "Ana");
  await userEvent.type(screen.getByLabelText("Last name"), "Meyer");
  await userEvent.type(screen.getByLabelText("Country code"), "rsa");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(posted).not.toBeNull());
  expect(posted!.country_code).toBe("rsa");
});

test("blocks a 2-letter country code before sending", async () => {
  server.use(http.get(api("/judges/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/judges/"), () => {
      called = true;
      return HttpResponse.json(makeJudge(), { status: 201 });
    }),
  );
  renderApp("/admin/judges");
  await userEvent.click(await screen.findByRole("button", { name: "New judge" }));
  await userEvent.type(screen.getByLabelText("First name"), "Ana");
  await userEvent.type(screen.getByLabelText("Last name"), "Meyer");
  await userEvent.type(screen.getByLabelText("Country code"), "RS");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Must be 3 letters")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("PATCHes only the changed field", async () => {
  server.use(
    http.get(api("/judges/"), () =>
      HttpResponse.json([makeJudge({ id: 7, first_name: "Naledi", last_name: "Dlamini" })]),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/judges/7"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeJudge({ id: 7 }));
    }),
  );
  renderApp("/admin/judges");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Naledi Dlamini" }));
  const brevet = screen.getByLabelText("Brevet");
  await userEvent.clear(brevet);
  await userEvent.type(brevet, "Cat II");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ brevet: "Cat II" }));
});

test("keeps the dialog open and shows the detail on a duplicate-identity 409", async () => {
  server.use(http.get(api("/judges/"), () => HttpResponse.json([])));
  server.use(
    http.post(api("/judges/"), () =>
      HttpResponse.json({ detail: "Judge already exists" }, { status: 409 }),
    ),
  );
  renderApp("/admin/judges");
  await userEvent.click(await screen.findByRole("button", { name: "New judge" }));
  await userEvent.type(screen.getByLabelText("First name"), "Ana");
  await userEvent.type(screen.getByLabelText("Last name"), "Meyer");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Judge already exists")).toBeInTheDocument();
  expect(screen.getByLabelText("First name")).toBeInTheDocument();
});

test("filters by country as a server round trip", async () => {
  const seen: (string | null)[] = [];
  server.use(
    http.get(api("/judges/"), ({ request }) => {
      seen.push(new URL(request.url).searchParams.get("country_code"));
      return HttpResponse.json([makeJudge({ id: 1, first_name: "Naledi", last_name: "Dlamini" })]);
    }),
  );
  renderApp("/admin/judges");
  expect(await screen.findByText("Naledi")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Country"), "BUL");
  await waitFor(() => expect(seen).toContain("BUL"));
});

test("search filters rows client-side without refetching", async () => {
  let calls = 0;
  server.use(
    http.get(api("/judges/"), () => {
      calls += 1;
      return HttpResponse.json([
        makeJudge({ id: 1, first_name: "Naledi", last_name: "Dlamini" }),
        makeJudge({ id: 2, first_name: "Elena", last_name: "Petrova" }),
      ]);
    }),
  );
  renderApp("/admin/judges");
  expect(await screen.findByText("Naledi")).toBeInTheDocument();
  const before = calls;
  await userEvent.type(screen.getByLabelText("Search"), "Petrova");
  await waitFor(() => expect(screen.queryByText("Naledi")).not.toBeInTheDocument());
  expect(screen.getByText("Elena")).toBeInTheDocument();
  expect(calls).toBe(before);
});
