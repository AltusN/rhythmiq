import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeMeet } from "../../fixtures";
import { api, server } from "../../msw/server";
import { renderApp } from "../../utils";

const apparatusRow = {
  rank: 1,
  entry_id: 21,
  routine_id: 77,
  competitor_name: "Aletta van der Merwe",
  bib_number: "12",
  level: "senior",
  age_group: "o14",
  apparatus: "hoop",
  d_score: "14.20",
  a_score: "8.90",
  e_score: "8.25",
  penalty: "0.10",
  total: "31.25",
  medal: "gold",
};

const allAroundRow = {
  rank: 1,
  entry_id: 21,
  competitor_name: "Aletta van der Merwe",
  bib_number: "12",
  level: "senior",
  age_group: "o14",
  total: "94.10",
  e_total: "24.60",
  routines_counted: 3,
  medal: null,
};

function mockStandings({ provisional = true } = {}) {
  server.use(
    http.get(api("/meets/:meetId"), () =>
      HttpResponse.json(makeMeet({ id: 5, status: provisional ? "in_progress" : "completed" })),
    ),
    http.get(api("/meets/:meetId/standings"), () =>
      HttpResponse.json({
        meet_id: 5,
        provisional,
        apparatus: "hoop",
        level: null,
        age_group: null,
        rankings: [apparatusRow],
      }),
    ),
    http.get(api("/meets/:meetId/all-around"), () =>
      HttpResponse.json({
        meet_id: 5,
        provisional,
        level: null,
        age_group: null,
        rankings: [allAroundRow],
      }),
    ),
  );
}

test("renders apparatus standings with scores and a provisional badge", async () => {
  mockStandings();
  renderApp("/meets/5/standings");
  expect(await screen.findByText("Aletta van der Merwe")).toBeInTheDocument();
  expect(screen.getByText("31.25")).toBeInTheDocument();
  expect(screen.getByText("gold")).toBeInTheDocument();
  expect(screen.getByText(/provisional/i)).toBeInTheDocument();
});

test("completed meet shows no provisional badge", async () => {
  mockStandings({ provisional: false });
  renderApp("/meets/5/standings");
  await screen.findByText("Aletta van der Merwe");
  expect(screen.queryByText(/provisional/i)).toBeNull();
});

test("all-around mode shows summed totals and routines counted", async () => {
  mockStandings();
  renderApp("/meets/5/standings");
  await screen.findByText("Aletta van der Merwe");
  await userEvent.click(screen.getByRole("button", { name: "All-around" }));
  expect(await screen.findByText("94.10")).toBeInTheDocument();
  expect(screen.getByText("3")).toBeInTheDocument();
});
