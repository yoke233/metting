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
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import { clampText, formatTimestamp, shortId, tryParseJson } from "@/lib/format"
import type { Meeting, Run } from "@/lib/types"

type RunControlPanelProps = {
  meeting: Meeting | null
  run: Run | null
  isStarting: boolean
  onStart: () => void
  runMode: "sequential" | "parallel"
  onRunModeChange: (mode: "sequential" | "parallel") => void
  parallelLimit: number
  onParallelLimitChange: (value: number) => void
  availableRoles: string[]
  parallelRoles: string[]
  onParallelRolesChange: (roles: string[]) => void
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
export function RunControlPanel({
  meeting,
  run,
  isStarting,
  onStart,
  runMode,
  onRunModeChange,
  parallelLimit,
  onParallelLimitChange,
  availableRoles,
  parallelRoles,
  onParallelRolesChange,
}: RunControlPanelProps) {
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
        <Separator />
        <div className="space-y-2 rounded-lg border bg-background/60 p-3 text-xs">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold">启动配置</div>
            <Badge variant="outline">{runMode === "parallel" ? "并行" : "串行"}</Badge>
          </div>
          <div className="flex items-center justify-between text-muted-foreground">
            <span>并行讨论</span>
            <Switch
              checked={runMode === "parallel"}
              onCheckedChange={(value) => onRunModeChange(value ? "parallel" : "sequential")}
            />
          </div>
          {runMode === "parallel" && (
            <div className="space-y-2 text-muted-foreground">
              <div>并行角色上限（0=不限）</div>
              <Input
                type="number"
                min={0}
                value={Number.isFinite(parallelLimit) ? String(parallelLimit) : "0"}
                onChange={(event) => {
                  const next = Number.parseInt(event.target.value || "0", 10)
                  onParallelLimitChange(Number.isNaN(next) ? 0 : Math.max(0, next))
                }}
              />
              <div className="text-[11px]">
                并行模式会在每轮生成投票与一致性评分，书记员会整理最终工件。
              </div>
              <div className="pt-1 text-xs">并行参与角色</div>
              <div className="flex flex-wrap gap-2">
                {availableRoles.map((role) => {
                  const active = parallelRoles.includes(role)
                  return (
                    <button
                      key={role}
                      type="button"
                      onClick={() => {
                        const next = active
                          ? parallelRoles.filter((item) => item !== role)
                          : [...parallelRoles, role]
                        onParallelRolesChange(next)
                      }}
                      className={`rounded-full border px-3 py-1 text-[11px] transition ${
                        active
                          ? "border-primary bg-primary/15 text-primary"
                          : "border-border/60 bg-background/70 text-muted-foreground"
                      }`}
                    >
                      {role}
                    </button>
                  )
                })}
                {!availableRoles.length && (
                  <div className="text-[11px] text-muted-foreground">暂无角色可选</div>
                )}
              </div>
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
