
export interface ScoutResult {
  scouter_name: string,
  secret_team_key: string,
  event_key: string,
  match_key: number,
  scouting_team: number,
  team_name: string | undefined,

  auto_nothing: boolean,
  auto_zone: boolean,
  auto_amp: number,
  auto_speaker: number,

  teleop_amp: number,
  teleop_speaker: number,

  endgame_park: boolean,
  endgame_onstage: boolean,
  endgame_harmony: boolean,
  endgame_trap: number,

  match_notes: string,
}
