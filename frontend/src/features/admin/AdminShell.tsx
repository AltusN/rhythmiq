import { NavLink, Outlet } from "react-router-dom";

/** Resources in dependency order — a district must exist before a club, and so on. */
const RESOURCES = [
  { path: "districts", label: "Districts" },
  { path: "clubs", label: "Clubs" },
  { path: "coaches", label: "Coaches" },
  { path: "groups", label: "Groups" },
  { path: "gymnasts", label: "Gymnasts" },
];

export function AdminShell() {
  return (
    <div className="flex gap-6">
      <nav className="w-44 shrink-0">
        <ul className="space-y-1">
          {RESOURCES.map((r) => (
            <li key={r.path}>
              <NavLink
                to={r.path}
                className={({ isActive }) =>
                  `block rounded px-3 py-1 text-sm ${
                    isActive ? "bg-blue-600 font-semibold text-white" : "hover:bg-gray-200"
                  }`
                }
              >
                {r.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <section className="min-w-0 flex-1">
        <Outlet />
      </section>
    </div>
  );
}
