import type { ArtifactSummary, EventRecord, Meeting, MemorySnapshot, Run } from "@/lib/types"

export const API_BASE = import.meta.env.VITE_API_BASE ?? ""

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init)
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`)
  }
  return (await res.json()) as T
}

export async function listMeetings(): Promise<Meeting[]> {
  const data = await request<{ meetings: Meeting[] }>("/meetings")
  return data.meetings ?? []
}

export async function listRuns(): Promise<Run[]> {
  const data = await request<{ runs: Run[] }>("/runs")
  return data.runs ?? []
}

export async function listEvents(
  run: Run,
  options: { includeTokens?: boolean } = {}
): Promise<EventRecord[]> {
  const includeTokens = options.includeTokens ?? true
  const params = new URLSearchParams()
  if (!includeTokens) {
    params.set("include_tokens", "false")
  }
  const query = params.toString()
  const data = await request<{ events: EventRecord[] }>(
    `/meetings/${run.meeting_id}/runs/${run.id}/events${query ? `?${query}` : ""}`
  )
  return data.events ?? []
}

export async function listSummaries(run: Run): Promise<ArtifactSummary[]> {
  const data = await request<{ summaries: ArtifactSummary[] }>(
    `/meetings/${run.meeting_id}/runs/${run.id}/summaries`
  )
  return data.summaries ?? []
}

export async function listMemories(run: Run) {
  const data = await request<{ memories: MemorySnapshot[] }>(
    `/meetings/${run.meeting_id}/runs/${run.id}/memories`
  )
  return data.memories ?? []
}

export async function getMemory(run: Run, role: string) {
  const data = await request<{ memory: Record<string, unknown> | null }>(
    `/meetings/${run.meeting_id}/runs/${run.id}/memories?role=${encodeURIComponent(role)}`
  )
  return data.memory
}

export async function createMeeting(payload: Record<string, unknown>) {
  return request<{ meeting_id: string }>(`/meetings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}

export async function startRun(meetingId: string, overrides?: Record<string, unknown>) {
  const init: RequestInit = { method: "POST" }
  if (overrides && Object.keys(overrides).length > 0) {
    init.headers = { "Content-Type": "application/json" }
    init.body = JSON.stringify({ overrides })
  }
  return request<{ run_id: string; status: string }>(`/meetings/${meetingId}/runs`, init)
}
