import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormDialog } from "../../../../src/features/admin/components/FormDialog";

test("renders with dialog semantics when open", () => {
  render(
    <FormDialog open title="Edit thing" onClose={vi.fn()}>
      <p>Body</p>
    </FormDialog>,
  );
  const dialog = screen.getByRole("dialog", { name: "Edit thing" });
  expect(dialog).toHaveAttribute("aria-modal", "true");
});

test("renders nothing when closed", () => {
  render(
    <FormDialog open={false} title="Edit thing" onClose={vi.fn()}>
      <p>Body</p>
    </FormDialog>,
  );
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("Escape closes the dialog", async () => {
  const onClose = vi.fn();
  render(
    <FormDialog open title="Edit thing" onClose={onClose}>
      <p>Body</p>
    </FormDialog>,
  );
  await userEvent.keyboard("{Escape}");
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("clicking the backdrop closes the dialog", async () => {
  const onClose = vi.fn();
  render(
    <FormDialog open title="Edit thing" onClose={onClose}>
      <p>Body</p>
    </FormDialog>,
  );
  // The backdrop is the dialog panel's parent — clicking it directly (not a
  // descendant) is what should trigger dismissal.
  const backdrop = screen.getByRole("dialog").parentElement as HTMLElement;
  await userEvent.click(backdrop);
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("clicking inside the dialog panel does not close it", async () => {
  const onClose = vi.fn();
  render(
    <FormDialog open title="Edit thing" onClose={onClose}>
      <p>Body content</p>
    </FormDialog>,
  );
  await userEvent.click(screen.getByText("Body content"));
  expect(onClose).not.toHaveBeenCalled();
});

// Guard only, not a behavioural test. jsdom has no layout engine, so it cannot be
// asked whether an over-tall panel puts Save out of reach — the actual bug this
// prevents (observed on the gymnast edit form at ~700px viewport height, where the
// title and both buttons overflowed off the ends of a non-scrolling fixed overlay).
// Asserting the classes at least fails loudly if someone strips them while restyling.
test("panel is height-capped and scrolls internally", () => {
  render(
    <FormDialog open title="Edit thing" onClose={vi.fn()}>
      <p>Body</p>
    </FormDialog>,
  );
  const dialog = screen.getByRole("dialog", { name: "Edit thing" });
  expect(dialog).toHaveClass("max-h-[90vh]");
  expect(dialog).toHaveClass("overflow-y-auto");
});
