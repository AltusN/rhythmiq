import { Link, Outlet } from "react-router-dom";

export function Layout() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <nav className="border-b border-gray-200 bg-white px-6 py-3">
        <Link to="/" className="text-lg font-bold">
          Rhythmiq
        </Link>
      </nav>
      <main className="mx-auto max-w-6xl p-6">
        <Outlet />
      </main>
    </div>
  );
}
