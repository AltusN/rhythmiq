import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PanelSetupDialog } from "../../../src/features/scoring/PanelSetupDialog";
import { makeJudge } from "../../fixtures";

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
  await userEvent.selectOptions(screen.getByLabelText("E1"), "2");
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
  await userEvent.selectOptions(screen.getByLabelText("E1"), "2");
  expect(screen.getByLabelText("E1")).toHaveValue("2");

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

  expect(screen.getByLabelText("E1")).toHaveValue("");
  expect(screen.getByLabelText("D")).toHaveValue("1");
});

test("clears a stale error when the dialog reopens", async () => {
  const judges = [
    makeJudge({ id: 1, first_name: "Naledi", last_name: "Dlamini" }),
    makeJudge({ id: 2, first_name: "Mina", last_name: "Kim" }),
  ];
  const props = { value: {}, judges, onSave: () => {}, onClose: () => {} };
  const { rerender } = render(<PanelSetupDialog open {...props} />);
  await userEvent.selectOptions(screen.getByLabelText("E1"), "2");
  await userEvent.selectOptions(screen.getByLabelText("E2"), "2");
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
  await userEvent.selectOptions(screen.getByLabelText("E1"), "2");
  await userEvent.selectOptions(screen.getByLabelText("E2"), "2");
  await userEvent.click(screen.getByRole("button", { name: "Save panel" }));

  expect(onSave).not.toHaveBeenCalled();
  expect(
    await screen.findByText("The same judge can't sit in two Execution slots."),
  ).toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText("E2"), "");
  await userEvent.click(screen.getByRole("button", { name: "Save panel" }));
  expect(onSave).toHaveBeenCalledWith({ E1: 2 });
});
