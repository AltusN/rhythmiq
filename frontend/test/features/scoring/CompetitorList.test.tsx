import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CompetitorList } from "../../../src/features/scoring/CompetitorList";
import { makeEntry } from "../../fixtures";

const entries = [
  makeEntry({ id: 1, bib_number: "11" }),
  makeEntry({ id: 2, bib_number: "12" }),
];
const baseProps = {
  entries,
  nameFor: (e: (typeof entries)[number]) => (e.id === 1 ? "Kea Botha" : "Aletta van der Merwe"),
  scoredTotals: new Map([[1, "24.85"]]),
  selectedEntryId: 2,
  onSelect: () => {},
  search: "",
  onSearchChange: () => {},
  level: "",
  onLevelChange: () => {},
  apparatus: "hoop",
  onApparatusChange: () => {},
};

describe("CompetitorList", () => {
  test("marks scored entries with their total and highlights the selection", () => {
    render(<CompetitorList {...baseProps} />);
    expect(screen.getByText(/24\.85/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /12 · Aletta/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
  });

  test("search filters by bib and name", () => {
    render(<CompetitorList {...baseProps} search="botha" />);
    expect(screen.getByText(/Kea Botha/)).toBeInTheDocument();
    expect(screen.queryByText(/Aletta/)).toBeNull();
  });

  test("clicking an entry selects it", async () => {
    const onSelect = vi.fn();
    render(<CompetitorList {...baseProps} onSelect={onSelect} />);
    await userEvent.click(screen.getByRole("button", { name: /11 · Kea Botha/ }));
    expect(onSelect).toHaveBeenCalledWith(entries[0]);
  });
});
