import { Link, Outlet } from "react-router-dom";

export function Layout() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <nav className="flex items-center gap-6 border-b border-gray-200 bg-white px-6 py-3">
        <Link to="/" className="text-lg font-bold">
          Rhythmiq
        </Link>
        <Link to="/" className="text-sm hover:underline">
          Meets
        </Link>
        <Link to="/admin" className="text-sm hover:underline">
          Admin
        </Link>
      </nav>
      <main className="mx-auto max-w-6xl p-6">
        <Outlet />
      </main>
    </div>
  );
}
