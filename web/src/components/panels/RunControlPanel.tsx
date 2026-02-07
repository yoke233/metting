import * as React from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { clampText, formatTimestamp, shortId, tryParseJson } from "@/lib/format"
import type { Meeting, Run } from "@/lib/types"

type RunControlPanelProps = {
  meeting: Meeting | null
  run: Run | null
  isStarting: boolean
  onStart: () => void
}

function renderStatus(status?: string | null) {
  // renderStatus: map status to badge for high-level overview.
  if (!status) return <Badge variant="outline">未选择</Badge>
  if (status === "DONE") return <Badge variant="secondary">已完成</Badge>
  if (status === "FAILED") return <Badge variant="destructive">失败</Badge>
  if (status === "PAUSED") return <Badge variant="outline">暂停</Badge>
  return <Badge>运行中</Badge>
}

// RunControlPanel: show selected meeting/run metadata and start actions.
export function RunControlPanel({ meeting, run, isStarting, onStart }: RunControlPanelProps) {
  const meetingConfig = React.useMemo(() => {
    // Parse meeting config for quick display.
    if (!meeting) return null
    return tryParseJson<Record<string, unknown>>(meeting.config_json)
  }, [meeting])

  const topic = meetingConfig && typeof meetingConfig.topic === "string" ? meetingConfig.topic : ""

  return (
    <Card className="border-muted/60 bg-card/80 shadow-lg">
      <CardHeader className="gap-2">
        <div className="flex items-center justify-between gap-4">
          <CardTitle className="text-lg">运行控制</CardTitle>
          {renderStatus(run?.status)}
        </div>
        <CardDescription>选择会议后启动新的 run。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">当前会议</div>
          <div className="font-semibold">
            {meeting ? meeting.title || clampText(topic, 48) || "未命名会议" : "—"}
          </div>
          {meeting && (
            <div className="text-xs text-muted-foreground">
              ID: {shortId(meeting.id, 8)} · 创建：{formatTimestamp(meeting.created_at)}
            </div>
          )}
        </div>
        <Separator />
        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">当前运行</div>
          <div className="font-semibold">{run ? `Run #${shortId(run.id, 6)}` : "—"}</div>
          {run && (
            <div className="text-xs text-muted-foreground">
              开始：{formatTimestamp(run.started_at)} · 结束：{formatTimestamp(run.ended_at)}
            </div>
          )}
        </div>
        <Button className="w-full" onClick={onStart} disabled={!meeting || isStarting}>
          {isStarting ? "启动中..." : "开始运行"}
        </Button>
      </CardContent>
    </Card>
  )
}
