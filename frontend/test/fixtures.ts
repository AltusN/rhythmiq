import type {
  ClubRead,
  DistrictRead,
  GroupRead,
  GymnastRead,
  JudgeRead,
  JudgeScoreRead,
  MeetEntryRead,
  MeetRead,
  RoutineRead,
} from "../src/api/types";

let nextId = 1000;
const id = () => nextId++;

export function makeMeet(overrides: Partial<MeetRead> = {}): MeetRead {
  return {
    id: id(),
    district_id: null,
    name: "Winter Cup",
    location: "Cape Town",
    start_date: "2026-08-01",
    end_date: "2026-08-02",
    status: "in_progress",
    medal_gold_min: null,
    medal_silver_min: null,
    ...overrides,
  };
}

export function makeGymnast(overrides: Partial<GymnastRead> = {}): GymnastRead {
  return {
    id: id(),
    club_id: null,
    group_id: null,
    first_name: "Aletta",
    last_name: "van der Merwe",
    date_of_birth: null,
    country_code: null,
    ...overrides,
  };
}

export function makeGroup(overrides: Partial<GroupRead> = {}): GroupRead {
  return { id: id(), club_id: 1, name: "Zvezda RG", ...overrides };
}

export function makeJudge(overrides: Partial<JudgeRead> = {}): JudgeRead {
  return {
    id: id(),
    first_name: "Naledi",
    last_name: "Dlamini",
    country_code: "RSA",
    brevet: null,
    ...overrides,
  };
}

export function makeEntry(overrides: Partial<MeetEntryRead> = {}): MeetEntryRead {
  return {
    id: id(),
    meet_id: 1,
    gymnast_id: 1,
    group_id: null,
    bib_number: "12",
    entry_fee_paid: false,
    age_group: "o14",
    level: "senior",
    ...overrides,
  };
}

export function makeRoutine(overrides: Partial<RoutineRead> = {}): RoutineRead {
  return {
    id: id(),
    entry_id: 1,
    apparatus: "hoop",
    order_of_performance: null,
    penalty: "0.00",
    ...overrides,
  };
}

export function makeDistrict(overrides: Partial<DistrictRead> = {}): DistrictRead {
  return { id: id(), name: "Western Cape", abbreviation: "WC", ...overrides };
}

export function makeClub(overrides: Partial<ClubRead> = {}): ClubRead {
  return {
    id: id(),
    district_id: 1,
    name: "Star Gymnastics",
    abbreviation: "STAR",
    ...overrides,
  };
}

export function makeScore(overrides: Partial<JudgeScoreRead> = {}): JudgeScoreRead {
  return {
    id: id(),
    routine_id: 1,
    judge_id: 1,
    panel: "execution",
    value: "8.00",
    ...overrides,
  };
}
