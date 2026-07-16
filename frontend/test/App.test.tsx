import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { api, server } from "./msw/server";
import { renderApp } from "./utils";

test("renders the nav shell", async () => {
  server.use(http.get(api("/meets/"), () => HttpResponse.json([])));
  renderApp("/");
  expect(await screen.findByText("Rhythmiq")).toBeInTheDocument();
});
