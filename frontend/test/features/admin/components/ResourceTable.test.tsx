import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResourceTable } from "../../../../src/features/admin/components/ResourceTable";

type Row = { id: number; name: string };
const rows: Row[] = [
  { id: 1, name: "Alpha" },
  { id: 2, name: "Beta" },
];
const columns = [{ header: "Name", render: (r: Row) => r.name }];

test("renders a row per item with labelled actions", async () => {
  const onEdit = vi.fn();
  const onDelete = vi.fn();
  render(
    <ResourceTable
      rows={rows}
      columns={columns}
      rowLabel={(r) => r.name}
      onEdit={onEdit}
      onDelete={onDelete}
      emptyMessage="Nothing here."
    />,
  );
  expect(screen.getByText("Alpha")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Edit Beta" }));
  expect(onEdit).toHaveBeenCalledWith(rows[1]);
  await userEvent.click(screen.getByRole("button", { name: "Delete Alpha" }));
  expect(onDelete).toHaveBeenCalledWith(rows[0]);
});

test("renders the empty message instead of a table when there are no rows", () => {
  render(
    <ResourceTable
      rows={[]}
      columns={columns}
      rowLabel={(r) => r.name}
      onEdit={vi.fn()}
      onDelete={vi.fn()}
      emptyMessage="Nothing here."
    />,
  );
  expect(screen.getByText("Nothing here.")).toBeInTheDocument();
  expect(screen.queryByRole("table")).toBeNull();
});
