import * as React from "react"

import { ModeToggle } from "@/components/mode-toggle"
import { StageView } from "@/components/pages/StageView"
import { EventStreamPanel } from "@/components/panels/EventStreamPanel"
import { MeetingsPanel } from "@/components/panels/MeetingsPanel"
import { MemoriesPanel } from "@/components/panels/MemoriesPanel"
import { RunControlPanel } from "@/components/panels/RunControlPanel"
import { RunsPanel } from "@/components/panels/RunsPanel"
import { SummariesPanel } from "@/components/panels/SummariesPanel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { createMeeting, listEvents, listMeetings, listMemories, listRuns, listSummaries, startRun } from "@/lib/api"
import { tryParseJson } from "@/lib/format"
import type { ArtifactSummary, EventRecord, Meeting, MemorySnapshot, Run } from "@/lib/types"

const AUTO_REFRESH_MS = 4000

const DEFAULT_MEETING_CONFIG = JSON.stringify(
  {
    title: "架构评审会议",
    topic: "会议系统对接 LangChain 并优化 UI",
    background: "基于现有后端与多角色协作流程，完成可视化控制台。",
    constraints: {
      交付周期: "2 周",
      资源限制: "前端 1 人",
      合规: "敏感信息不出域",
    },
    roles: ["Chief Architect", "Infra Architect", "Security Architect", "Skeptic", "Recorder"],
    max_rounds: 8,
    context_mode: "layered",
    termination: {
      min_rounds: 8,
      open_questions_max: 2,
      disagreements_max: 1,
    },
    output_schema: "v2",
    pause_on_round: null,
    role_prompts: {},
  },
  null,
  2
)

// App: orchestrate dashboard state and data fetching.
function App() {
  const [meetings, setMeetings] = React.useState<Meeting[]>([])
  const [runs, setRuns] = React.useState<Run[]>([])
  const [view, setView] = React.useState<"console" | "stage">(() =>
    window.location.hash === "#/stage" ? "stage" : "console"
  )
  const [selectedMeetingId, setSelectedMeetingId] = React.useState<string | null>(null)
  const [selectedRunId, setSelectedRunId] = React.useState<string | null>(null)
  const [events, setEvents] = React.useState<EventRecord[]>([])
  const [summaries, setSummaries] = React.useState<ArtifactSummary[]>([])
  const [memories, setMemories] = React.useState<MemorySnapshot[]>([])
  const [selectedRole, setSelectedRole] = React.useState<string | null>(null)
  const [draftConfig, setDraftConfig] = React.useState(DEFAULT_MEETING_CONFIG)
  const [createError, setCreateError] = React.useState<string | null>(null)
  const [showTokens, setShowTokens] = React.useState(true)
  const [autoRefresh, setAutoRefresh] = React.useState(false)
  const [isCreating, setIsCreating] = React.useState(false)
  const [isStarting, setIsStarting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [statusNote, setStatusNote] = React.useState<string | null>(null)

  const selectedMeeting = React.useMemo(
    () => meetings.find((meeting) => meeting.id === selectedMeetingId) ?? null,
    [meetings, selectedMeetingId]
  )

  const runsForMeeting = React.useMemo(() => {
    return selectedMeetingId ? runs.filter((run) => run.meeting_id === selectedMeetingId) : runs
  }, [runs, selectedMeetingId])

  const selectedRun = React.useMemo(
    () => runs.find((run) => run.id === selectedRunId) ?? null,
    [runs, selectedRunId]
  )

  const refreshMeetings = React.useCallback(async () => {
    // refreshMeetings: fetch and cache meeting list.
    setError(null)
    try {
      const data = await listMeetings()
      setMeetings(data)
    } catch (err) {
      setError("加载会议列表失败")
    }
  }, [])

  const refreshRuns = React.useCallback(async () => {
    // refreshRuns: fetch and cache run list.
    setError(null)
    try {
      const data = await listRuns()
      setRuns(data)
    } catch (err) {
      setError("加载运行记录失败")
    }
  }, [])

  const refreshRunData = React.useCallback(async (run: Run) => {
    // refreshRunData: fetch events, summaries, and memories for a run.
    setError(null)
    try {
      const [eventData, summaryData, memoryData] = await Promise.all([
        listEvents(run),
        listSummaries(run),
        listMemories(run),
      ])
      setEvents(eventData)
      setSummaries(summaryData)
      setMemories(memoryData)
    } catch (err) {
      setError("加载运行详情失败")
    }
  }, [])

  const refreshAll = React.useCallback(async () => {
    // refreshAll: synchronize meeting + run lists.
    await Promise.all([refreshMeetings(), refreshRuns()])
    setStatusNote("已刷新最新数据")
  }, [refreshMeetings, refreshRuns])

  const handleCreateMeeting = React.useCallback(async () => {
    // handleCreateMeeting: validate JSON and post new meeting config.
    setCreateError(null)
    setError(null)
    const payload = tryParseJson<Record<string, unknown>>(draftConfig)
    if (!payload) {
      setCreateError("配置 JSON 无法解析")
      return
    }
    if (typeof payload.topic !== "string" || !payload.topic.trim()) {
      setCreateError("配置需要包含 topic 字段")
      return
    }
    setIsCreating(true)
    try {
      await createMeeting(payload)
      setStatusNote("会议已创建")
      await refreshMeetings()
    } catch (err) {
      setCreateError("创建会议失败")
    } finally {
      setIsCreating(false)
    }
  }, [draftConfig, refreshMeetings])

  const handleStartRun = React.useCallback(async () => {
    // handleStartRun: start a run for the selected meeting.
    if (!selectedMeeting) {
      setError("请先选择会议")
      return
    }
    setIsStarting(true)
    setError(null)
    try {
      const result = await startRun(selectedMeeting.id)
      setStatusNote("已启动会议运行")
      await refreshRuns()
      setSelectedRunId(result.run_id)
      handleSwitchView("stage")
    } catch (err) {
      setError("启动会议失败")
    } finally {
      setIsStarting(false)
    }
  }, [refreshRuns, selectedMeeting])

  const handleSelectMeeting = React.useCallback((meetingId: string) => {
    // handleSelectMeeting: switch active meeting and reset run focus.
    setSelectedMeetingId(meetingId)
  }, [])

  const handleSwitchView = React.useCallback((next: "console" | "stage") => {
    // handleSwitchView: sync SPA view with hash navigation.
    window.location.hash = next === "stage" ? "#/stage" : "#/"
    setView(next)
  }, [])

  const handleDraftChange = React.useCallback((value: string) => {
    // handleDraftChange: update draft JSON and clear validation errors.
    setDraftConfig(value)
    if (createError) {
      setCreateError(null)
    }
  }, [createError])

  const handleSelectRun = React.useCallback(
    (runId: string) => {
      // handleSelectRun: set active run and sync meeting selection.
      setSelectedRunId(runId)
      const run = runs.find((item) => item.id === runId)
      if (run) {
        setSelectedMeetingId(run.meeting_id)
      }
    },
    [runs]
  )

  React.useEffect(() => {
    void refreshAll()
  }, [refreshAll])

  React.useEffect(() => {
    const handleHashChange = () => {
      setView(window.location.hash === "#/stage" ? "stage" : "console")
    }
    window.addEventListener("hashchange", handleHashChange)
    return () => window.removeEventListener("hashchange", handleHashChange)
  }, [])

  React.useEffect(() => {
    if (!meetings.length) {
      setSelectedMeetingId(null)
      return
    }
    if (!selectedMeetingId || !meetings.some((meeting) => meeting.id === selectedMeetingId)) {
      setSelectedMeetingId(meetings[0].id)
    }
  }, [meetings, selectedMeetingId])

  React.useEffect(() => {
    if (!runsForMeeting.length) {
      setSelectedRunId(null)
      return
    }
    if (!selectedRunId || !runsForMeeting.some((run) => run.id === selectedRunId)) {
      setSelectedRunId(runsForMeeting[0].id)
    }
  }, [runsForMeeting, selectedRunId])

  React.useEffect(() => {
    if (!selectedRun) {
      setEvents([])
      setSummaries([])
      setMemories([])
      return
    }
    void refreshRunData(selectedRun)
  }, [refreshRunData, selectedRun])

  React.useEffect(() => {
    if (!memories.length) {
      setSelectedRole(null)
      return
    }
    if (!selectedRole || !memories.some((item) => item.role_name === selectedRole)) {
      setSelectedRole(memories[0].role_name)
    }
  }, [memories, selectedRole])

  React.useEffect(() => {
    if (!autoRefresh || !selectedRun) return
    const handle = window.setInterval(() => {
      void refreshRunData(selectedRun)
    }, AUTO_REFRESH_MS)
    return () => window.clearInterval(handle)
  }, [autoRefresh, refreshRunData, selectedRun])

  React.useEffect(() => {
    if (!statusNote) return
    const handle = window.setTimeout(() => setStatusNote(null), 3600)
    return () => window.clearTimeout(handle)
  }, [statusNote])

  return (
    <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(1200px_520px_at_-10%_-10%,rgba(16,185,129,0.18),transparent),radial-gradient(900px_520px_at_110%_0%,rgba(234,179,8,0.14),transparent)]">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-24 top-12 h-72 w-72 rounded-full bg-primary/15 blur-3xl" />
        <div className="absolute right-0 top-32 h-80 w-80 rounded-full bg-accent/20 blur-3xl" />
      </div>
      <div className="relative mx-auto flex min-h-screen w-full flex-col gap-6 px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-6">
          <div className="space-y-3">
            <div className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
              GROUP CHAT CONSOLE
            </div>
            <div className="text-3xl font-semibold">会议系统控制台</div>
            <div className="text-sm text-muted-foreground">
              统一查看会议、运行、事件流与角色记忆，支持一键启动与自动刷新。
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">LangChain</Badge>
              <Badge variant="secondary">Layered Context</Badge>
              <Badge variant="outline">Event Stream</Badge>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant={view === "console" ? "default" : "outline"}
              size="sm"
              onClick={() => handleSwitchView("console")}
            >
              控制台
            </Button>
            <Button
              variant={view === "stage" ? "default" : "outline"}
              size="sm"
              onClick={() => handleSwitchView("stage")}
            >
              舞台视图
            </Button>
            <Button variant="outline" size="sm" onClick={refreshAll}>
              刷新全部
            </Button>
            <ModeToggle />
          </div>
        </header>

        {statusNote && (
          <div className="rounded-xl border border-emerald-200/50 bg-emerald-50/60 px-4 py-2 text-sm text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200">
            {statusNote}
          </div>
        )}
        {error && (
          <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        {view === "stage" ? (
          <StageView meeting={selectedMeeting} run={selectedRun} />
        ) : (
          <main className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
            <section className="space-y-6">
              <MeetingsPanel
                meetings={meetings}
                selectedId={selectedMeetingId}
                draftConfig={draftConfig}
                isCreating={isCreating}
                createError={createError}
                onSelect={handleSelectMeeting}
                onRefresh={refreshMeetings}
                onDraftChange={handleDraftChange}
                onCreate={handleCreateMeeting}
                onResetTemplate={() => {
                  setDraftConfig(DEFAULT_MEETING_CONFIG)
                  setCreateError(null)
                }}
              />
              <RunControlPanel
                meeting={selectedMeeting}
                run={selectedRun}
                isStarting={isStarting}
                onStart={handleStartRun}
              />
              <RunsPanel
                runs={runsForMeeting}
                selectedId={selectedRunId}
                onSelect={handleSelectRun}
                onRefresh={refreshRuns}
              />
            </section>

            <section className="space-y-6">
              <EventStreamPanel
                events={events}
                showTokens={showTokens}
                autoRefresh={autoRefresh}
                onToggleTokens={setShowTokens}
                onToggleAutoRefresh={setAutoRefresh}
                onRefresh={() => {
                  if (selectedRun) {
                    void refreshRunData(selectedRun)
                  }
                }}
                className="min-h-[520px]"
              />
              <div className="grid gap-6 lg:grid-cols-2">
                <SummariesPanel summaries={summaries} />
                <MemoriesPanel
                  memories={memories}
                  selectedRole={selectedRole}
                  onSelectRole={setSelectedRole}
                />
              </div>
            </section>
          </main>
        )}
      </div>
    </div>
  )
}

export default App
