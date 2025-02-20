
export interface ScoutResult {
  scouter_name: string,
  secret_team_key: string,
  event_key: string,
  match_key: number,
  scouting_team: number,
  team_name: string | undefined,

  auto_nothing: boolean,
  auto_left_line: boolean,
  auto_coral4: number,
  auto_coral3: number,
  auto_coral2: number,
  auto_coral1: number,
  auto_processor: number,
  auto_barge: number,

  teleop_coral4: number,
  teleop_coral3: number,
  teleop_coral2: number,
  teleop_coral1: number,
  teleop_processor: number,
  teleop_barge: number,

  endgame_park: boolean,
  endgame_hang_shallow: boolean,
  endgame_hang_deep: boolean,

  match_notes: string,
}
