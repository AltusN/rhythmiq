import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { CompetitorCombobox, matchesNamePartPrefix } from "../../../src/features/entries/CompetitorCombobox";

describe("matchesNamePartPrefix", () => {
  it("matches when any name part starts with the query, case-insensitively", () => {
    expect(matchesNamePartPrefix("Leah Geyer", "Le")).toBe(true);
    expect(matchesNamePartPrefix("Leah Geyer", "ge")).toBe(true); // surname, case-insensitive
    expect(matchesNamePartPrefix("Leah Geyer", "ah")).toBe(false); // not a start
    expect(matchesNamePartPrefix("Leah Geyer", "")).toBe(true); // empty matches all
  });
});

function Harness({ options }: { options: { id: number; label: string }[] }) {
  const [value, setValue] = useState("");
  return (
    <>
      <CompetitorCombobox options={options} value={value} onChange={setValue} ariaLabel="Competitor" />
      <span data-testid="value">{value}</span>
    </>
  );
}

const OPTIONS = [
  { id: 7, label: "Leah Geyer" },
  { id: 8, label: "Liam Botha" },
  { id: 9, label: "Ella Johannes" },
];

it("filters the list as the user types and selects on click", async () => {
  const user = userEvent.setup();
  render(<Harness options={OPTIONS} />);

  await user.type(screen.getByLabelText("Competitor"), "Le");
  const list = screen.getByRole("listbox");
  expect(within(list).getByText("Leah Geyer")).toBeInTheDocument();
  expect(within(list).queryByText("Liam Botha")).toBeNull(); // "Li" would match, "Le" doesn't
  expect(within(list).queryByText("Ella Johannes")).toBeNull();

  await user.click(within(list).getByText("Leah Geyer"));
  expect(screen.getByTestId("value")).toHaveTextContent("7");
  expect(screen.getByLabelText("Competitor")).toHaveValue("Leah Geyer");
});

it("selects the highlighted option with the keyboard", async () => {
  const user = userEvent.setup();
  render(<Harness options={OPTIONS} />);

  const input = screen.getByLabelText("Competitor");
  await user.type(input, "Li"); // matches "Liam Botha"
  await user.keyboard("{ArrowDown}{Enter}");
  expect(screen.getByTestId("value")).toHaveTextContent("8");
});

it("closes the list on Escape without changing the value", async () => {
  const user = userEvent.setup();
  render(<Harness options={OPTIONS} />);

  await user.type(screen.getByLabelText("Competitor"), "Le");
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(screen.getByTestId("value")).toHaveTextContent("");
});
