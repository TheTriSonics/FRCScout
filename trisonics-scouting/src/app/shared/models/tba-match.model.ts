type AllianceChoices = 'blue' | 'red';

export interface Link {
  nodes: number[]
  row: string
}

export interface Video {
  key: string
  type: string
}

export interface AutoCommunity {
  B: string[]
  M: string[]
  T: string[]
}

export interface TeleopCommunity {
  B: string[]
  M: string[]
  T: string[]
}

export interface TBAAlliance {
  dq_team_keys: string[]
  score: number
  surrogate_team_keys: string[]
  team_keys: string[]
}

export interface TBAScoreBreakdown {
  activationBonusAchieved: boolean
  adjustPoints: number
  autoBridgeState: string
  autoChargeStationPoints: number
  autoChargeStationRobot1: string
  autoChargeStationRobot2: string
  autoChargeStationRobot3: string
  autoCommunity: AutoCommunity
  autoDocked: boolean
  autoGamePieceCount: number
  autoGamePiecePoints: number
  autoMobilityPoints: number
  autoPoints: number
  coopGamePieceCount: number
  coopertitionCriteriaMet: boolean
  endGameBridgeState: string
  endGameChargeStationPoints: number
  endGameChargeStationRobot1: string
  endGameChargeStationRobot2: string
  endGameChargeStationRobot3: string
  endGameParkPoints: number
  extraGamePieceCount: number
  foulCount: number
  foulPoints: number
  g405Penalty: boolean
  h111Penalty: boolean
  linkPoints: number
  links: Link[]
  mobilityRobot1: string
  mobilityRobot2: string
  mobilityRobot3: string
  rp: number
  sustainabilityBonusAchieved: boolean
  techFoulCount: number
  teleopCommunity: TeleopCommunity
  teleopGamePieceCount: number
  teleopGamePiecePoints: number
  teleopPoints: number
  totalChargeStationPoints: number
  totalPoints: number
}

export interface TBAMatch {
  actual_time: number
  alliances: Record<AllianceChoices, TBAAlliance>
  comp_level: string
  event_key: string
  key: string
  match_number: number
  post_result_time: number
  predicted_time: number
  score_breakdown: TBAScoreBreakdown
  set_number: number
  time: number
  videos: Video[]
  winning_alliance: string
}
