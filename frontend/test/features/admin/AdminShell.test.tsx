import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { api, server } from "../../msw/server";
import { renderApp } from "../../utils";

test("/admin redirects to districts and shows the resource sidebar", async () => {
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  renderApp("/admin");
  expect(await screen.findByRole("heading", { name: "Districts" })).toBeInTheDocument();
  for (const name of ["Districts", "Clubs", "Coaches", "Groups", "Gymnasts"]) {
    expect(screen.getByRole("link", { name })).toBeInTheDocument();
  }
});

test("the top nav links to meets and admin", async () => {
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  renderApp("/admin/districts");
  expect(await screen.findByRole("link", { name: "Meets" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Admin" })).toBeInTheDocument();
});
