import * as React from "react"

import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { API_BASE, listEvents } from "@/lib/api"
import { clampText, formatTimestamp, shortId, tryParseJson } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { EventRecord, Meeting, Run } from "@/lib/types"

type StreamEvent = EventRecord & { id: number }

type RoleMessage = {
  id: string
  content: string
  ts: number
  round?: number
}

type RoleState = {
  role: string
  streamText: string
  streamMessageId: string | null
  lastTokenTs: number | null
  lastMessageTs: number | null
  messages: RoleMessage[]
}

type State = {
  roles: Record<string, RoleState>
  order: string[]
}

type Action =
  | { type: "reset"; roles: string[] }
  | { type: "token"; role: string; messageId: string; text: string; ts: number }
  | { type: "message"; role: string; messageId: string; content: string; ts: number; round?: number }

type StageViewProps = {
  meeting: Meeting | null
  run: Run | null
}

const MAX_MESSAGES = 120
const SPEAKING_WINDOW_MS = 2500
const RECENT_WINDOW_MS = 9000

const ROLE_LABELS: Record<string, string> = {
  "Chief Architect": "首席架构师",
  "Infra Architect": "基础设施架构师",
  "Security Architect": "安全架构师",
  Skeptic: "质疑者",
  Recorder: "书记员",
}

function useNow(intervalMs = 1000) {
  // useNow: shared timer for status indicators.
  const [now, setNow] = React.useState(() => Date.now())
  React.useEffect(() => {
    const handle = window.setInterval(() => setNow(Date.now()), intervalMs)
    return () => window.clearInterval(handle)
  }, [intervalMs])
  return now
}

function ensureRole(state: State, role: string) {
  if (state.roles[role]) return state
  const next: State = {
    roles: {
      ...state.roles,
      [role]: {
        role,
        streamText: "",
        streamMessageId: null,
        lastTokenTs: null,
        lastMessageTs: null,
        messages: [],
      },
    },
    order: state.order.includes(role) ? state.order : [...state.order, role],
  }
  return next
}

function stageReducer(state: State, action: Action): State {
  // stageReducer: update role timelines from streaming events.
  if (action.type === "reset") {
    const roles = action.roles ?? []
    const roleMap: Record<string, RoleState> = {}
    roles.forEach((role) => {
      roleMap[role] = {
        role,
        streamText: "",
        streamMessageId: null,
        lastTokenTs: null,
        lastMessageTs: null,
        messages: [],
      }
    })
    return { roles: roleMap, order: roles }
  }

  let next = ensureRole(state, action.role)
  const roleState = next.roles[action.role]
  if (!roleState) return next

  if (action.type === "token") {
    const sameMessage = roleState.streamMessageId === action.messageId
    const streamText = sameMessage ? roleState.streamText + action.text : action.text
    const updated: RoleState = {
      ...roleState,
      streamText,
      streamMessageId: action.messageId,
      lastTokenTs: action.ts,
    }
    return { ...next, roles: { ...next.roles, [action.role]: updated } }
  }

  if (action.type === "message") {
    const messages = [...roleState.messages, {
      id: action.messageId,
      content: action.content,
      ts: action.ts,
      round: action.round,
    }]
    const trimmed = messages.slice(-MAX_MESSAGES)
    const updated: RoleState = {
      ...roleState,
      messages: trimmed,
      lastMessageTs: action.ts,
      streamText: roleState.streamMessageId === action.messageId ? "" : roleState.streamText,
      streamMessageId:
        roleState.streamMessageId === action.messageId ? null : roleState.streamMessageId,
    }
    return { ...next, roles: { ...next.roles, [action.role]: updated } }
  }

  return next
}

function resolveRole(event: StreamEvent): string {
  // resolveRole: infer role names from event payloads.
  const payload = event.payload ?? {}
  const payloadRole = payload.role
  if (typeof payloadRole === "string" && payloadRole.trim()) {
    return payloadRole
  }
  const message = payload.message
  if (message && typeof message.name === "string" && message.name.trim()) {
    return message.name
  }
  const actor = event.actor ?? ""
  if (actor.includes(":")) {
    const parts = actor.split(":")
    return parts.slice(1).join(":") || actor
  }
  return actor || "unknown"
}

function getMessageId(event: StreamEvent): string {
  const payload = event.payload ?? {}
  const messageId = payload.message_id
  return messageId ? String(messageId) : `msg-${event.id}`
}

function getMessageContent(event: StreamEvent): string {
  const payload = event.payload ?? {}
  const message = payload.message
  if (message && typeof message.content === "string") {
    return message.content
  }
  return ""
}

function getRoundIndex(event: StreamEvent): number | undefined {
  const payload = event.payload ?? {}
  const round = payload.round
  return typeof round === "number" ? round : undefined
}

function roleStatus(role: RoleState, now: number) {
  if (role.lastTokenTs && now - role.lastTokenTs <= SPEAKING_WINDOW_MS) {
    return "speaking"
  }
  if (role.lastMessageTs && now - role.lastMessageTs <= RECENT_WINDOW_MS) {
    return "recent"
  }
  return "idle"
}

function statusLabel(status: string) {
  if (status === "speaking") return "正在发言"
  if (status === "recent") return "刚刚发言"
  return "待机"
}

export function StageView({ meeting, run }: StageViewProps) {
  // StageView: stage-style role viewer with streaming speech.
  const baseRoles = React.useMemo(() => {
    if (!meeting) return []
    const config = tryParseJson<Record<string, unknown>>(meeting.config_json) ?? {}
    const roles = Array.isArray(config.roles) ? config.roles.map(String) : []
    return roles.length ? roles : []
  }, [meeting])

  const [state, dispatch] = React.useReducer(stageReducer, {
    roles: {},
    order: baseRoles,
  })
  const [selectedRole, setSelectedRole] = React.useState<string | null>(
    baseRoles[0] ?? null
  )
  const [connection, setConnection] = React.useState<"idle" | "connecting" | "open" | "error">(
    "idle"
  )
  const now = useNow(800)
  const selectedRoleRef = React.useRef<string | null>(null)
  const autoFollowRef = React.useRef<{ messageId: string; ts: number }>({
    messageId: "",
    ts: 0,
  })

  React.useEffect(() => {
    dispatch({ type: "reset", roles: baseRoles })
    setSelectedRole(baseRoles[0] ?? null)
  }, [baseRoles])

  React.useEffect(() => {
    selectedRoleRef.current = selectedRole
  }, [selectedRole])

  React.useEffect(() => {
    if (!selectedRole && state.order.length) {
      setSelectedRole(state.order[0])
      return
    }
    if (selectedRole && !state.order.includes(selectedRole)) {
      setSelectedRole(state.order[0] ?? null)
    }
  }, [selectedRole, state.order])

  const seenMessageIdsRef = React.useRef<Set<string>>(new Set())

  React.useEffect(() => {
    if (!run) return
    dispatch({ type: "reset", roles: baseRoles })
    seenMessageIdsRef.current.clear()
    autoFollowRef.current = { messageId: "", ts: 0 }
    setConnection("connecting")

    const maybeAutoFollow = (role: string, messageId: string, ts: number) => {
      // Auto-focus the role that starts speaking to match stage behavior.
      if (!role || role.toLowerCase() === "user") return
      if (selectedRoleRef.current === role) return
      const nowMs = ts || Date.now()
      if (nowMs - autoFollowRef.current.ts < 800) return
      if (autoFollowRef.current.messageId === messageId) return
      autoFollowRef.current = { messageId, ts: nowMs }
      setSelectedRole(role)
    }

    const loadHistory = async () => {
      // Load historical agent messages without token payloads.
      try {
        const history = await listEvents(run, { includeTokens: false })
        history.forEach((event) => {
          if (event.type !== "agent_message") return
          const streamEvent = event as StreamEvent
          const role = resolveRole(streamEvent)
          if (!role || role.toLowerCase() === "user") return
          const messageId = getMessageId(streamEvent)
          if (seenMessageIdsRef.current.has(messageId)) return
          seenMessageIdsRef.current.add(messageId)
          const content = getMessageContent(streamEvent)
          dispatch({
            type: "message",
            role,
            messageId,
            content,
            ts: event.ts_ms,
            round: getRoundIndex(streamEvent),
          })
        })
      } catch {
        setConnection("error")
      }
    }

    void loadHistory()

    const url = `${API_BASE}/meetings/${run.meeting_id}/runs/${run.id}/events/stream?tail=300&poll_ms=500`
    const source = new EventSource(url)

    source.onopen = () => setConnection("open")
    source.onerror = () => setConnection("error")

    source.onmessage = (event) => {
      if (!event.data) return
      const payload = JSON.parse(event.data) as StreamEvent
      const role = resolveRole(payload)
      if (payload.type === "token") {
        if (!role || role.toLowerCase() === "user") return
        const text = String(payload.payload?.text ?? "")
        if (text) {
          const messageId = getMessageId(payload)
          maybeAutoFollow(role, messageId, payload.ts_ms)
          dispatch({
            type: "token",
            role,
            messageId,
            text,
            ts: payload.ts_ms,
          })
        }
        return
      }
      if (payload.type === "agent_message") {
        if (!role || role.toLowerCase() === "user") return
        const messageId = getMessageId(payload)
        maybeAutoFollow(role, messageId, payload.ts_ms)
        if (seenMessageIdsRef.current.has(messageId)) return
        seenMessageIdsRef.current.add(messageId)
        const content = getMessageContent(payload)
        dispatch({
          type: "message",
          role,
          messageId,
          content,
          ts: payload.ts_ms,
          round: getRoundIndex(payload),
        })
      }
    }

    return () => {
      source.close()
      setConnection("idle")
    }
  }, [run, baseRoles])

  const roles = state.order.length ? state.order : Object.keys(state.roles)
  const selected = selectedRole ? state.roles[selectedRole] : undefined

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
            STAGE VIEW
          </div>
          <div className="text-2xl font-semibold">角色发言舞台</div>
          <div className="text-sm text-muted-foreground">
            {meeting ? meeting.title || "未命名会议" : "未选择会议"} ·{" "}
            {run ? `Run #${shortId(run.id, 6)}` : "未选择运行"}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={connection === "open" ? "secondary" : "outline"}>
            {connection === "open" && "已连接"}
            {connection === "connecting" && "连接中"}
            {connection === "error" && "连接异常"}
            {connection === "idle" && "未连接"}
          </Badge>
          {run && (
            <Badge variant="outline">开始：{formatTimestamp(run.started_at)}</Badge>
          )}
        </div>
      </div>

      {!run && (
        <div className="rounded-2xl border border-dashed bg-card/60 p-6 text-sm text-muted-foreground">
          请选择一条运行记录后进入舞台视图。
        </div>
      )}

      {run && (
        <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
          <aside className="space-y-3">
            {roles.map((role) => {
              const stateRole = state.roles[role]
              const status = stateRole ? roleStatus(stateRole, now) : "idle"
              const isActive = role === selectedRole
              return (
                <button
                  key={role}
                  type="button"
                  onClick={() => setSelectedRole(role)}
                  className={cn(
                    "w-full rounded-2xl border p-4 text-left transition",
                    isActive
                      ? "border-primary bg-primary/10 text-primary shadow-md"
                      : "border-border/70 bg-card/80 text-foreground"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        "relative flex h-12 w-12 items-center justify-center rounded-full text-lg font-semibold",
                        status === "speaking" && "bg-primary/20 text-primary ring-2 ring-primary",
                        status === "recent" && "bg-accent/20 text-accent-foreground",
                        status === "idle" && "bg-muted text-muted-foreground"
                      )}
                    >
                      <span>{ROLE_LABELS[role]?.slice(0, 1) ?? role.slice(0, 1)}</span>
                      {status === "speaking" && (
                        <span className="absolute -bottom-1 -right-1 h-3 w-3 rounded-full bg-primary shadow-[0_0_12px_rgba(16,185,129,0.6)]" />
                      )}
                    </div>
                    <div>
                      <div className="text-sm font-semibold">
                        {ROLE_LABELS[role] ?? role}
                      </div>
                      <div className="text-xs text-muted-foreground">{statusLabel(status)}</div>
                    </div>
                  </div>
                  {stateRole?.messages.length ? (
                    <div className="mt-3 text-xs text-muted-foreground">
                      最近：{clampText(stateRole.messages.at(-1)?.content ?? "", 48)}
                    </div>
                  ) : (
                    <div className="mt-3 text-xs text-muted-foreground">暂无发言</div>
                  )}
                </button>
              )
            })}
          </aside>

          <section className="space-y-5">
            <div className="rounded-2xl border bg-card/80 p-4 shadow-lg">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-base font-semibold">正在发言</div>
                <Badge variant="outline">
                  {selected ? ROLE_LABELS[selected.role] ?? selected.role : "未选择角色"}
                </Badge>
              </div>
              <div className="mt-3 min-h-[140px] whitespace-pre-wrap text-sm text-muted-foreground">
                {selected?.streamText
                  ? selected.streamText
                  : "暂无流式输出，等待下一条发言。"}
              </div>
            </div>

            <div className="rounded-2xl border bg-card/80 p-4 shadow-lg">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-base font-semibold">发言记录</div>
                <Badge variant="secondary">{selected?.messages.length ?? 0} 条</Badge>
              </div>
              <ScrollArea className="mt-4 h-[460px] pr-2">
                <div className="space-y-3">
                  {selected?.messages.map((msg, index) => (
                    <details key={`${msg.id}-${index}`} open={index === selected.messages.length - 1}>
                      <summary className="cursor-pointer rounded-lg border border-border/60 bg-background/60 px-3 py-2 text-sm font-semibold">
                        <span className="mr-2 text-muted-foreground">
                          {msg.round ? `第${msg.round}轮` : "发言"}
                        </span>
                        {clampText(msg.content, 80)}
                      </summary>
                      <div className="mt-2 whitespace-pre-wrap rounded-lg border border-dashed bg-background/70 p-3 text-sm text-muted-foreground">
                        {msg.content}
                      </div>
                    </details>
                  ))}
                  {!selected?.messages.length && (
                    <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
                      暂无历史发言。
                    </div>
                  )}
                </div>
              </ScrollArea>
            </div>
          </section>
        </div>
      )}
    </section>
  )
}
