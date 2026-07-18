import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeDistrict } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

test("lists districts", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([
        makeDistrict({ id: 1, name: "Western Cape", abbreviation: "WC" }),
        makeDistrict({ id: 2, name: "Gauteng", abbreviation: "GAU" }),
      ]),
    ),
  );
  renderApp("/admin/districts");
  expect(await screen.findByText("Western Cape")).toBeInTheDocument();
  expect(screen.getByText("GAU")).toBeInTheDocument();
});

test("shows an empty message when there are no districts", async () => {
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  renderApp("/admin/districts");
  expect(await screen.findByText("No districts yet.")).toBeInTheDocument();
});

test("surfaces a list error", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json({ detail: "Database unavailable" }, { status: 500 }),
    ),
  );
  renderApp("/admin/districts");
  expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable");
});

test("creates a district", async () => {
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/districts/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeDistrict(), { status: 201 });
    }),
  );
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "New district" }));
  await userEvent.type(screen.getByLabelText("Name"), "Free State");
  await userEvent.type(screen.getByLabelText("Abbreviation"), "FS");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({ name: "Free State", abbreviation: "FS" }),
  );
});

test("blocks an over-long abbreviation before sending", async () => {
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/districts/"), () => {
      called = true;
      return HttpResponse.json(makeDistrict(), { status: 201 });
    }),
  );
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "New district" }));
  await userEvent.type(screen.getByLabelText("Name"), "Free State");
  await userEvent.type(screen.getByLabelText("Abbreviation"), "TOOMANYCHARS");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("At most 10 characters")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("keeps the dialog open and shows the detail on a 409", async () => {
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  server.use(
    http.post(api("/districts/"), () =>
      HttpResponse.json({ detail: "District abbreviation already exists" }, { status: 409 }),
    ),
  );
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "New district" }));
  await userEvent.type(screen.getByLabelText("Name"), "Gauteng");
  await userEvent.type(screen.getByLabelText("Abbreviation"), "GAU");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("already exists");
  expect(screen.getByLabelText("Name")).toHaveValue("Gauteng");
});

test("edits a district, sending only the changed field", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([makeDistrict({ id: 4, name: "Gauteng", abbreviation: "GAU" })]),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  let patchedId: string | undefined;
  server.use(
    http.patch(api("/districts/:districtId"), async ({ request, params }) => {
      patched = (await request.json()) as Record<string, unknown>;
      patchedId = params.districtId as string;
      return HttpResponse.json(makeDistrict({ id: 4 }));
    }),
  );
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Gauteng" }));
  const name = screen.getByLabelText("Name");
  expect(name).toHaveValue("Gauteng");
  await userEvent.clear(name);
  await userEvent.type(name, "Gauteng North");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ name: "Gauteng North" }));
  expect(patchedId).toBe("4");
});

test("reopening the dialog for another row resets the fields", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([
        makeDistrict({ id: 1, name: "Western Cape", abbreviation: "WC" }),
        makeDistrict({ id: 2, name: "Gauteng", abbreviation: "GAU" }),
      ]),
    ),
  );
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Western Cape" }));
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await userEvent.click(await screen.findByRole("button", { name: "Edit Gauteng" }));
  expect(screen.getByLabelText("Name")).toHaveValue("Gauteng");
});

test("deletes a district after confirmation", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([makeDistrict({ id: 4, name: "Gauteng" })]),
    ),
  );
  let deletedId: string | undefined;
  server.use(
    http.delete(api("/districts/:districtId"), ({ params }) => {
      deletedId = params.districtId as string;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Gauteng" }));
  await waitFor(() => expect(deletedId).toBe("4"));
  expect(confirmSpy.mock.calls[0][0]).toContain("Gauteng");
  confirmSpy.mockRestore();
});

test("declining the confirm aborts the delete", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([makeDistrict({ id: 4, name: "Gauteng" })]),
    ),
  );
  let called = false;
  server.use(
    http.delete(api("/districts/:districtId"), () => {
      called = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Gauteng" }));
  expect(called).toBe(false);
  confirmSpy.mockRestore();
});

test("shows the API detail when a delete is blocked by dependents", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([makeDistrict({ id: 4, name: "Gauteng" })]),
    ),
  );
  server.use(
    http.delete(api("/districts/:districtId"), () =>
      HttpResponse.json(
        { detail: "Cannot delete district with existing clubs" },
        { status: 409 },
      ),
    ),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Gauteng" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("existing clubs");
  confirmSpy.mockRestore();
});

test("clears a stale delete error when a save succeeds", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([makeDistrict({ id: 4, name: "Gauteng" })]),
    ),
  );
  server.use(
    http.delete(api("/districts/:districtId"), () =>
      HttpResponse.json(
        { detail: "Cannot delete district with existing clubs" },
        { status: 409 },
      ),
    ),
  );
  server.use(
    http.post(api("/districts/"), async () => {
      return HttpResponse.json(makeDistrict({ id: 5, name: "Free State" }), { status: 201 });
    }),
  );
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([
        makeDistrict({ id: 4, name: "Gauteng" }),
        makeDistrict({ id: 5, name: "Free State" }),
      ]),
    ),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/districts");
  // Step 1: Delete fails with 409, error shows in banner
  await userEvent.click(await screen.findByRole("button", { name: "Delete Gauteng" }));
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("existing clubs");
  confirmSpy.mockRestore();
  // Step 2: Create a new district, which succeeds
  await userEvent.click(screen.getByRole("button", { name: "New district" }));
  await userEvent.type(screen.getByLabelText("Name"), "Free State");
  await userEvent.type(screen.getByLabelText("Abbreviation"), "FS");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  // Step 3: Wait for the dialog to close by verifying Free State appears in the table
  await waitFor(() => {
    expect(screen.getByText("Free State")).toBeInTheDocument();
  });
  // The old delete error should no longer appear in the banner
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("search filters districts client-side", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([
        makeDistrict({ id: 1, name: "Western Cape", abbreviation: "WC" }),
        makeDistrict({ id: 2, name: "Gauteng", abbreviation: "GAU" }),
      ]),
    ),
  );
  renderApp("/admin/districts");
  await screen.findByText("Western Cape");
  await userEvent.type(screen.getByLabelText("Search"), "gau");
  expect(screen.queryByText("Western Cape")).toBeNull();
  expect(screen.getByText("Gauteng")).toBeInTheDocument();
});
