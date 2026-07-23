import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PanelSetupDialog } from "../../../src/features/scoring/PanelSetupDialog";
import type { JudgeRead } from "../../../src/api/types";
import { makeJudge } from "../../fixtures";

const judge = (id: number, first_name: string) =>
  ({ id, first_name, last_name: "Judge", country_code: null, category: null }) as JudgeRead;

test("saves selected judges per slot, leaving unpicked slots unassigned", async () => {
  const judges = [
    makeJudge({ id: 1, first_name: "Naledi", last_name: "Dlamini" }),
    makeJudge({ id: 2, first_name: "Mina", last_name: "Kim" }),
  ];
  const onSave = vi.fn();
  render(
    <PanelSetupDialog open value={{}} judges={judges} onSave={onSave} onClose={() => {}} />,
  );
  await userEvent.selectOptions(screen.getByLabelText("D"), "1");
  // E1 is rendered once per band that uses it (4-7 and 8+ both do), all bound to the
  // same underlying slot — picking either instance updates the same draft value.
  await userEvent.selectOptions(screen.getAllByLabelText("E1")[0], "2");
  await userEvent.click(screen.getByRole("button", { name: "Save panel" }));
  expect(onSave).toHaveBeenCalledWith({ D: 1, E1: 2 });
});

test("renders nothing when closed", () => {
  const { container } = render(
    <PanelSetupDialog open={false} value={{}} judges={[]} onSave={() => {}} onClose={() => {}} />,
  );
  expect(container).toBeEmptyDOMElement();
});

test("discards abandoned edits and re-seeds from value on reopen", async () => {
  const judges = [
    makeJudge({ id: 1, first_name: "Naledi", last_name: "Dlamini" }),
    makeJudge({ id: 2, first_name: "Mina", last_name: "Kim" }),
  ];
  const { rerender } = render(
    <PanelSetupDialog
      open
      value={{ D: 1 }}
      judges={judges}
      onSave={() => {}}
      onClose={() => {}}
    />,
  );
  await userEvent.selectOptions(screen.getAllByLabelText("E1")[0], "2");
  for (const el of screen.getAllByLabelText("E1")) expect(el).toHaveValue("2");

  rerender(
    <PanelSetupDialog
      open={false}
      value={{ D: 1 }}
      judges={judges}
      onSave={() => {}}
      onClose={() => {}}
    />,
  );
  rerender(
    <PanelSetupDialog
      open
      value={{ D: 1 }}
      judges={judges}
      onSave={() => {}}
      onClose={() => {}}
    />,
  );

  for (const el of screen.getAllByLabelText("E1")) expect(el).toHaveValue("");
  expect(screen.getByLabelText("D")).toHaveValue("1");
});

test("clears a stale error when the dialog reopens", async () => {
  const judges = [
    makeJudge({ id: 1, first_name: "Naledi", last_name: "Dlamini" }),
    makeJudge({ id: 2, first_name: "Mina", last_name: "Kim" }),
  ];
  const props = { value: {}, judges, onSave: () => {}, onClose: () => {} };
  const { rerender } = render(<PanelSetupDialog open {...props} />);
  await userEvent.selectOptions(screen.getAllByLabelText("E1")[0], "2");
  await userEvent.selectOptions(screen.getAllByLabelText("E2")[0], "2");
  await userEvent.click(screen.getByRole("button", { name: "Save panel" }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();

  rerender(<PanelSetupDialog open={false} {...props} />);
  rerender(<PanelSetupDialog open {...props} />);

  expect(screen.queryByRole("alert")).toBeNull();
});

test("blocks save and shows an inline error when the same judge fills two E slots", async () => {
  const judges = [
    makeJudge({ id: 1, first_name: "Naledi", last_name: "Dlamini" }),
    makeJudge({ id: 2, first_name: "Mina", last_name: "Kim" }),
  ];
  const onSave = vi.fn();
  render(
    <PanelSetupDialog open value={{}} judges={judges} onSave={onSave} onClose={() => {}} />,
  );
  await userEvent.selectOptions(screen.getAllByLabelText("E1")[0], "2");
  await userEvent.selectOptions(screen.getAllByLabelText("E2")[0], "2");
  await userEvent.click(screen.getByRole("button", { name: "Save panel" }));

  expect(onSave).not.toHaveBeenCalled();
  expect(
    await screen.findByText("The same judge can't sit in two Execution slots."),
  ).toBeInTheDocument();

  await userEvent.selectOptions(screen.getAllByLabelText("E2")[0], "");
  await userEvent.click(screen.getByRole("button", { name: "Save panel" }));
  expect(onSave).toHaveBeenCalledWith({ E1: 2 });
});

it("groups the slots by scoring band", async () => {
  render(
    <PanelSetupDialog
      open
      value={{}}
      judges={[judge(1, "Ann"), judge(2, "Bo")]}
      onSave={vi.fn()}
      onClose={vi.fn()}
    />,
  );

  expect(screen.getByText(/Levels 1–3/)).toBeInTheDocument();
  expect(screen.getByText(/Levels 4–7/)).toBeInTheDocument();
  expect(screen.getByText(/Levels 8\+/)).toBeInTheDocument();
  expect(screen.getByLabelText("F1")).toBeInTheDocument();
  expect(screen.getByLabelText("F2")).toBeInTheDocument();
  expect(screen.getByLabelText("F3")).toBeInTheDocument();
  expect(screen.getByLabelText("F4")).toBeInTheDocument();
  expect(screen.getByLabelText("DB1")).toBeInTheDocument();
  expect(screen.getByLabelText("A2")).toBeInTheDocument();
});

it("rejects the same judge in two difficulty-body slots", async () => {
  const onSave = vi.fn();
  const user = userEvent.setup();
  render(
    <PanelSetupDialog
      open
      value={{}}
      judges={[judge(1, "Ann"), judge(2, "Bo")]}
      onSave={onSave}
      onClose={vi.fn()}
    />,
  );

  await user.selectOptions(screen.getByLabelText("DB1"), "1");
  await user.selectOptions(screen.getByLabelText("DB2"), "1");
  await user.click(screen.getByRole("button", { name: "Save panel" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The same judge can't sit in two Difficulty (Body) slots.",
  );
  expect(onSave).not.toHaveBeenCalled();
});

it("rejects the same judge in two artistry slots", async () => {
  const onSave = vi.fn();
  const user = userEvent.setup();
  render(
    <PanelSetupDialog
      open
      value={{}}
      judges={[judge(1, "Ann"), judge(2, "Bo")]}
      onSave={onSave}
      onClose={vi.fn()}
    />,
  );

  await user.selectOptions(screen.getByLabelText("A1"), "2");
  await user.selectOptions(screen.getByLabelText("A2"), "2");
  await user.click(screen.getByRole("button", { name: "Save panel" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The same judge can't sit in two Artistry slots.",
  );
  expect(onSave).not.toHaveBeenCalled();
});
