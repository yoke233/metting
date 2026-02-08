import * as React from "react"

import { MermaidBlock } from "@/components/MermaidBlock"
import { MarkdownBlock } from "@/components/MarkdownBlock"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Switch } from "@/components/ui/switch"
import { cn } from "@/lib/utils"
import type { EventRecord } from "@/lib/types"

type EventLine = {
  id: string
  label: string
  kind: "markdown" | "json" | "mermaid"
  content: string
}

type EventStreamPanelProps = {
  events: EventRecord[]
  showTokens: boolean
  autoRefresh: boolean
  className?: string
  onToggleTokens: (value: boolean) => void
  onToggleAutoRefresh: (value: boolean) => void
  onRefresh: () => void
}

const fmt = (obj: unknown) => JSON.stringify(obj, null, 2)

function buildEventLines(events: EventRecord[], showTokens: boolean): EventLine[] {
  // buildEventLines: map raw events into display-friendly lines.
  const lines: EventLine[] = []
  const tokenBuffers: Record<string, string> = {}

  events.forEach((event, index) => {
    const payload = event.payload ?? {}
    if (event.type === "token") {
      if (!showTokens) return
      const messageId = String(payload.message_id ?? "unknown")
      const key = `${messageId}:${event.actor ?? "agent"}`
      tokenBuffers[key] = (tokenBuffers[key] ?? "") + String(payload.text ?? "")
      return
    }

    if (event.type === "agent_message" && showTokens) {
      const messageId = String(payload.message_id ?? "unknown")
      const key = `${messageId}:${event.actor ?? "agent"}`
      if (tokenBuffers[key]) {
        lines.push({
          id: `${index}-stream-${messageId}`,
          label: `token_stream · ${event.actor ?? "agent"}`,
          kind: "markdown",
          content: tokenBuffers[key],
        })
        delete tokenBuffers[key]
      }
    }

    let detail = ""
    if (event.type === "round_started") detail = ` round=${payload.round ?? ""}`
    if (event.type === "speaker_selected") detail = ` speakers=${payload.speakers ?? payload.speaker ?? ""}`
    if (event.type === "agent_message") {
      const message = payload.message
      const text =
        message && typeof message === "object" && typeof (message as { content?: unknown }).content === "string"
          ? String((message as { content?: unknown }).content)
          : ""
      detail = ` message="${String(text).slice(0, 42)}"`
    }
    if (event.type === "artifact_written") detail = ` artifact=${payload.artifact_type ?? ""}`
    if (event.type === "summary_written") detail = " summary"
    if (event.type === "metric") {
      const consensus = payload.consensus_score !== undefined ? ` consensus=${payload.consensus_score}` : ""
      detail = ` open_q=${payload.open_questions_count ?? ""} disagree=${payload.disagreements_count ?? ""}${consensus}`
    }

    let kind: EventLine["kind"] = "json"
    let content = ""
    if (event.type === "agent_message") {
      kind = "markdown"
      const message = payload.message
      content =
        message && typeof message === "object" && typeof (message as { content?: unknown }).content === "string"
          ? String((message as { content?: unknown }).content)
          : ""
    } else if (event.type === "summary_written") {
      kind = "markdown"
      content = payload.content ? fmt(payload.content) : ""
    } else if (event.type === "artifact_written") {
      const artifact =
        payload.content && typeof payload.content === "object"
          ? (payload.content as Record<string, unknown>)
          : {}
      if (typeof artifact.mermaid === "string") {
        kind = "mermaid"
        content = artifact.mermaid
      } else {
        kind = "json"
        content = fmt(artifact)
      }
    } else {
      kind = "json"
      content = fmt(event)
    }

    lines.push({
      id: `${index}-${event.type}`,
      label: `[${event.type}]${detail}`.trim(),
      kind,
      content,
    })
  })

  if (showTokens) {
    Object.entries(tokenBuffers).forEach(([key, value]) => {
      lines.push({
        id: `stream-tail-${key}`,
        label: `token_stream · ${key.split(":")[1] ?? "agent"}`,
        kind: "markdown",
        content: value,
      })
    })
  }

  return lines
}

export function EventStreamPanel({
  events,
  showTokens,
  autoRefresh,
  className,
  onToggleTokens,
  onToggleAutoRefresh,
  onRefresh,
}: EventStreamPanelProps) {
  // EventStreamPanel: left list + right detail view for event replay.
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const lines = React.useMemo(() => buildEventLines(events, showTokens), [events, showTokens])
  const selected = React.useMemo(
    () => lines.find((line) => line.id === selectedId) ?? lines[0],
    [lines, selectedId]
  )

  React.useEffect(() => {
    if (!selectedId && lines.length) {
      setSelectedId(lines[0].id)
    }
  }, [lines, selectedId])

  return (
    <Card className={cn("border-muted/60 bg-card/80 shadow-lg", className)}>
      <CardHeader className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <CardTitle className="text-lg">事件流</CardTitle>
          <Badge variant="secondary">{lines.length} 条</Badge>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Switch checked={showTokens} onCheckedChange={onToggleTokens} />
            显示流式 Token
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Switch checked={autoRefresh} onCheckedChange={onToggleAutoRefresh} />
            自动刷新
          </div>
          <Button variant="outline" size="sm" onClick={onRefresh}>
            刷新
          </Button>
        </div>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)]">
        <ScrollArea className="h-[420px] rounded-xl border bg-background/60 p-2">
          <div className="space-y-2">
            {lines.map((line) => (
              <button
                key={line.id}
                type="button"
                onClick={() => setSelectedId(line.id)}
                className={`w-full rounded-lg border px-3 py-2 text-left text-xs transition ${
                  selected?.id === line.id
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border/70 bg-card/80 text-foreground"
                }`}
              >
                {line.label}
              </button>
            ))}
            {!lines.length && (
              <div className="rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">
                暂无事件
              </div>
            )}
          </div>
        </ScrollArea>
        <div className="rounded-xl border bg-background/60 p-4">
          {!selected && <div className="text-sm text-muted-foreground">请选择事件查看详情。</div>}
          {selected?.kind === "mermaid" && <MermaidBlock code={selected.content} />}
          {selected?.kind === "markdown" && <MarkdownBlock text={selected.content} />}
          {selected?.kind === "json" && (
            <pre className="whitespace-pre-wrap text-xs text-muted-foreground">
              {selected.content}
            </pre>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
