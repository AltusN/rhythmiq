import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeEntry, makeGroup, makeGymnast, makeMeet } from "../../fixtures";
import { api, server } from "../../msw/server";
import { renderApp } from "../../utils";

function mockBase({ meet = makeMeet({ id: 5 }), entries = [] as unknown[] } = {}) {
  server.use(
    http.get(api("/meets/:meetId"), () => HttpResponse.json(meet)),
    http.get(api("/meet-entries/"), () => HttpResponse.json(entries)),
    http.get(api("/gymnasts/"), () =>
      HttpResponse.json([makeGymnast({ id: 7, first_name: "Lindiwe", last_name: "Nkosi" })]),
    ),
    http.get(api("/groups/"), () =>
      HttpResponse.json([makeGroup({ id: 3, name: "Zvezda RG" })]),
    ),
  );
}

test("lists entries with competitor names", async () => {
  mockBase({
    entries: [makeEntry({ meet_id: 5, gymnast_id: 7, group_id: null, bib_number: "12" })],
  });
  renderApp("/meets/5/entries");
  expect(await screen.findByText("Lindiwe Nkosi")).toBeInTheDocument();
  expect(screen.getByText("12")).toBeInTheDocument();
});

test("creates a gymnast entry and refreshes the list", async () => {
  mockBase();
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/meet-entries/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeEntry({ meet_id: 5, gymnast_id: 7 }), { status: 201 });
    }),
  );
  renderApp("/meets/5/entries");
  await screen.findByRole("button", { name: "Add entry" });
  await userEvent.click(screen.getByRole("button", { name: "Add entry" }));
  await userEvent.selectOptions(screen.getByLabelText("Competitor"), "7");
  await userEvent.type(screen.getByLabelText("Bib number"), "31");
  await userEvent.selectOptions(screen.getByLabelText("Level"), "senior");
  await userEvent.selectOptions(screen.getByLabelText("Age group"), "o14");
  await userEvent.click(screen.getByRole("button", { name: "Create entry" }));
  await waitFor(() =>
    expect(posted).toMatchObject({
      meet_id: 5,
      gymnast_id: 7,
      group_id: null,
      bib_number: "31",
      level: "senior",
      age_group: "o14",
    }),
  );
});

test("shows the API detail on a bib conflict", async () => {
  mockBase();
  server.use(
    http.post(api("/meet-entries/"), () =>
      HttpResponse.json({ detail: "Bib number 12 already used in this meet" }, { status: 409 }),
    ),
  );
  renderApp("/meets/5/entries");
  await userEvent.click(await screen.findByRole("button", { name: "Add entry" }));
  await userEvent.selectOptions(screen.getByLabelText("Competitor"), "7");
  await userEvent.type(screen.getByLabelText("Bib number"), "12");
  await userEvent.selectOptions(screen.getByLabelText("Level"), "senior");
  await userEvent.selectOptions(screen.getByLabelText("Age group"), "o14");
  await userEvent.click(screen.getByRole("button", { name: "Create entry" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("already used");
});

test("deletes an entry after confirmation", async () => {
  const entry = makeEntry({ meet_id: 5, gymnast_id: 7, group_id: null });
  mockBase({ entries: [entry] });
  let deleted = false;
  server.use(
    http.delete(api("/meet-entries/:entryId"), () => {
      deleted = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/meets/5/entries");
  await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
  await waitFor(() => expect(deleted).toBe(true));
  confirmSpy.mockRestore();
});

test("delete confirm names the competitor when there is no bib, and declining aborts", async () => {
  const entry = makeEntry({ meet_id: 5, gymnast_id: 7, group_id: null, bib_number: null });
  mockBase({ entries: [entry] });
  let deleted = false;
  server.use(
    http.delete(api("/meet-entries/:entryId"), () => {
      deleted = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
  renderApp("/meets/5/entries");
  await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
  expect(confirmSpy).toHaveBeenCalledOnce();
  const message = confirmSpy.mock.calls[0][0] as string;
  expect(message).toContain("Lindiwe Nkosi");
  expect(message).not.toContain("null");
  expect(deleted).toBe(false);
  confirmSpy.mockRestore();
});

test("completed meet hides entry management", async () => {
  mockBase({
    meet: makeMeet({ id: 5, status: "completed" }),
    entries: [makeEntry({ meet_id: 5, gymnast_id: 7, group_id: null })],
  });
  renderApp("/meets/5/entries");
  await screen.findByText("Lindiwe Nkosi");
  expect(screen.queryByRole("button", { name: "Add entry" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
});
