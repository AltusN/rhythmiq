import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiDetail, client } from "../../api/client";
import { ErrorBanner } from "../../components/ErrorBanner";
import { labelize } from "../../lib/domain";

export function MeetListPage() {
  const { data, error, isPending } = useQuery({
    queryKey: ["meets"],
    queryFn: async () => {
      const { data, error } = await client.GET("/meets/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  if (isPending) return <p>Loading…</p>;
  if (error) return <ErrorBanner message={error.message} />;

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Meets</h1>
      <ul className="divide-y divide-gray-200 rounded border border-gray-200 bg-white">
        {data.map((meet) => (
          <li key={meet.id}>
            <Link
              to={`/meets/${meet.id}`}
              className="flex items-center justify-between px-4 py-3 hover:bg-gray-50"
            >
              <span>
                {meet.name}{" "}
                <span className="text-sm text-gray-500">
                  {meet.location} · {meet.start_date}
                </span>
              </span>
              <span className="rounded bg-gray-100 px-2 py-1 text-xs">
                {labelize(meet.status)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
