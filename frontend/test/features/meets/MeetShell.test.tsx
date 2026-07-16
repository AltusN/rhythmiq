import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeMeet } from "../../fixtures";
import { api, server } from "../../msw/server";
import { renderApp } from "../../utils";

function mockMeet(meet: ReturnType<typeof makeMeet>) {
  server.use(
    http.get(api("/meets/:meetId"), () => HttpResponse.json(meet)),
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
