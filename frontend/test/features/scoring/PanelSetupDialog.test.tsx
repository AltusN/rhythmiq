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
