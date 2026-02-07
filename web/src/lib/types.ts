export type Meeting = {
  id: string
  title: string
  config_json: string
  created_at: number
}

export type Run = {
  id: string
  meeting_id: string
  status: string
  config_json: string
  started_at: number
  ended_at: number | null
}

export type EventRecord = {
  run_id: string
  ts_ms: number
  type: string
  actor: string
  payload: Record<string, unknown>
}

export type ArtifactSummary = {
  run_id: string
  type: string
  version: string
  content: Record<string, unknown>
  created_ts_ms: number
}

export type MemorySnapshot = {
  role_name: string
  content: Record<string, unknown>
  updated_ts_ms: number
}
