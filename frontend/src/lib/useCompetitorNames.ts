import { useQuery } from "@tanstack/react-query";
import { apiDetail, client } from "../api/client";
import type { GroupRead, GymnastRead, MeetEntryRead } from "../api/types";

export function useCompetitorNames() {
  const gymnastsQ = useQuery({
    queryKey: ["gymnasts"],
    queryFn: async () => {
      const { data, error } = await client.GET("/gymnasts/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });
  const groupsQ = useQuery({
    queryKey: ["groups"],
    queryFn: async () => {
      const { data, error } = await client.GET("/groups/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const gymnasts: GymnastRead[] = gymnastsQ.data ?? [];
  const groups: GroupRead[] = groupsQ.data ?? [];

  const nameFor = (entry: MeetEntryRead): string => {
    if (entry.gymnast_id != null) {
      const g = gymnasts.find((g) => g.id === entry.gymnast_id);
      return g ? `${g.first_name} ${g.last_name}` : `Gymnast #${entry.gymnast_id}`;
    }
    const grp = groups.find((g) => g.id === entry.group_id);
    return grp ? grp.name : `Group #${entry.group_id}`;
  };

  return {
    nameFor,
    gymnasts,
    groups,
    isPending: gymnastsQ.isPending || groupsQ.isPending,
  };
}
