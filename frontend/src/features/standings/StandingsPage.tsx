import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { apiDetail, client, toNum } from "../../api/client";
import type { AgeGroup, Apparatus, Level, MeetRead } from "../../api/types";
import { ErrorBanner } from "../../components/ErrorBanner";
import { AGE_GROUPS, APPARATUS, LEVELS, labelize } from "../../lib/domain";

export const POLL_MS = 5000;

const fmt = (v: number | string) => toNum(v).toFixed(2);

export function StandingsPage() {
  const meet = useOutletContext<MeetRead>();
  const [mode, setMode] = useState<"apparatus" | "all-around">("apparatus");
  const [apparatus, setApparatus] = useState<Apparatus>("hoop");
  const [level, setLevel] = useState("");
  const [ageGroup, setAgeGroup] = useState("");

  const query = {
    level: (level || undefined) as Level | undefined,
    age_group: (ageGroup || undefined) as AgeGroup | undefined,
  };

  const apparatusQ = useQuery({
    queryKey: ["standings", meet.id, "apparatus", apparatus, level, ageGroup],
    enabled: mode === "apparatus",
    refetchInterval: POLL_MS,
    queryFn: async () => {
      const { data, error } = await client.GET("/meets/{meet_id}/standings", {
        params: { path: { meet_id: meet.id }, query: { apparatus, ...query } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const allAroundQ = useQuery({
    queryKey: ["standings", meet.id, "all-around", level, ageGroup],
    enabled: mode === "all-around",
    refetchInterval: POLL_MS,
    queryFn: async () => {
      const { data, error } = await client.GET("/meets/{meet_id}/all-around", {
        params: { path: { meet_id: meet.id }, query },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const active = mode === "apparatus" ? apparatusQ : allAroundQ;
  const provisional = active.data?.provisional ?? true;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="flex overflow-hidden rounded border border-gray-300">
          {(["apparatus", "all-around"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-3 py-1 text-sm capitalize ${
                mode === m ? "bg-blue-600 font-semibold text-white" : "bg-white"
              }`}
            >
              {m === "all-around" ? "All-around" : "Apparatus"}
            </button>
          ))}
        </div>
        {mode === "apparatus" && (
          <select
            aria-label="Apparatus"
            value={apparatus}
            onChange={(e) => setApparatus(e.target.value as Apparatus)}
            className="rounded border border-gray-300 p-1 text-sm"
          >
            {APPARATUS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        )}
        <select
          aria-label="Level filter"
          value={level}
          onChange={(e) => setLevel(e.target.value)}
          className="rounded border border-gray-300 p-1 text-sm"
        >
          <option value="">All levels</option>
          {LEVELS.map((l) => (
            <option key={l} value={l}>
              {labelize(l)}
            </option>
          ))}
        </select>
        <select
          aria-label="Age group filter"
          value={ageGroup}
          onChange={(e) => setAgeGroup(e.target.value)}
          className="rounded border border-gray-300 p-1 text-sm"
        >
          <option value="">All age groups</option>
          {AGE_GROUPS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        {provisional && active.data && (
          <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
            provisional
          </span>
        )}
      </div>

      {active.error && <ErrorBanner message={active.error.message} />}
      {active.isPending && <p>Loading…</p>}

      {mode === "apparatus" && apparatusQ.data && (
        <table className="w-full rounded border border-gray-200 bg-white text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-gray-500">
              <th className="p-2">Rank</th>
              <th className="p-2">Bib</th>
              <th className="p-2">Competitor</th>
              <th className="p-2">Level</th>
              <th className="p-2 text-right">D</th>
              <th className="p-2 text-right">A</th>
              <th className="p-2 text-right">E</th>
              <th className="p-2 text-right">Pen</th>
              <th className="p-2 text-right">Total</th>
              <th className="p-2">Medal</th>
            </tr>
          </thead>
          <tbody>
            {apparatusQ.data.rankings.map((row) => (
              <tr key={row.routine_id} className="border-t border-gray-100">
                <td className="p-2">{row.rank}</td>
                <td className="p-2">{row.bib_number}</td>
                <td className="p-2">{row.competitor_name}</td>
                <td className="p-2">{labelize(row.level)}</td>
                <td className="p-2 text-right">{fmt(row.d_score)}</td>
                <td className="p-2 text-right">{fmt(row.a_score)}</td>
                <td className="p-2 text-right">{fmt(row.e_score)}</td>
                <td className="p-2 text-right">{fmt(row.penalty)}</td>
                <td className="p-2 text-right font-semibold">{fmt(row.total)}</td>
                <td className="p-2">{row.medal ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {mode === "all-around" && allAroundQ.data && (
        <table className="w-full rounded border border-gray-200 bg-white text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-gray-500">
              <th className="p-2">Rank</th>
              <th className="p-2">Bib</th>
              <th className="p-2">Competitor</th>
              <th className="p-2">Level</th>
              <th className="p-2 text-right">Total</th>
              <th className="p-2 text-right">Routines</th>
              <th className="p-2">Medal</th>
            </tr>
          </thead>
          <tbody>
            {allAroundQ.data.rankings.map((row) => (
              <tr key={row.entry_id} className="border-t border-gray-100">
                <td className="p-2">{row.rank}</td>
                <td className="p-2">{row.bib_number}</td>
                <td className="p-2">{row.competitor_name}</td>
                <td className="p-2">{labelize(row.level)}</td>
                <td className="p-2 text-right font-semibold">{fmt(row.total)}</td>
                <td className="p-2 text-right">{row.routines_counted}</td>
                <td className="p-2">{row.medal ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
