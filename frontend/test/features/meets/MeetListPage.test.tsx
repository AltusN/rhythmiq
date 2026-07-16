import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { makeMeet } from "../../fixtures";
import { api, server } from "../../msw/server";
import { renderApp } from "../../utils";

test("lists meets with status badges", async () => {
  server.use(
    http.get(api("/meets/"), () =>
      HttpResponse.json([
        makeMeet({ name: "Winter Cup", status: "in_progress" }),
        makeMeet({ name: "Spring Trials", status: "draft" }),
      ]),
    ),
  );
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
  renderApp("/");
  expect(await screen.findByRole("alert")).toHaveTextContent("boom");
});
