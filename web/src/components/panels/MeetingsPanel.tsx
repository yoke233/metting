import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { clampText, formatTimestamp, shortId, tryParseJson } from "@/lib/format"
import type { Meeting } from "@/lib/types"

type MeetingMeta = {
  topic: string
  roles: string[]
  maxRounds?: number
  contextMode?: string
  parallelMode?: boolean
}

type MeetingsPanelProps = {
  meetings: Meeting[]
  selectedId: string | null
  draftConfig: string
  isCreating: boolean
  createError?: string | null
  onSelect: (id: string) => void
  onRefresh: () => void
  onDraftChange: (value: string) => void
  onCreate: () => void
  onResetTemplate: () => void
}

function extractMeetingMeta(meeting: Meeting): MeetingMeta {
  // extractMeetingMeta: parse config_json for lightweight UI hints.
  const raw = tryParseJson<Record<string, unknown>>(meeting.config_json) ?? {}
  const topic = typeof raw.topic === "string" ? raw.topic : ""
  const roles = Array.isArray(raw.roles) ? raw.roles.map(String) : []
  const maxRounds = typeof raw.max_rounds === "number" ? raw.max_rounds : undefined
  const contextMode = typeof raw.context_mode === "string" ? raw.context_mode : undefined
  const parallelMode = typeof raw.parallel_mode === "boolean" ? raw.parallel_mode : undefined
  return { topic, roles, maxRounds, contextMode, parallelMode }
}

// MeetingsPanel: show meeting list and creation form.
export function MeetingsPanel({
  meetings,
  selectedId,
  draftConfig,
  isCreating,
  createError,
  onSelect,
  onRefresh,
  onDraftChange,
  onCreate,
  onResetTemplate,
}: MeetingsPanelProps) {
  return (
    <Card className="border-muted/60 bg-card/80 shadow-lg">
      <CardHeader className="gap-2">
        <div className="flex items-center justify-between gap-4">
          <CardTitle className="text-lg">会议列表</CardTitle>
          <Button variant="outline" size="sm" onClick={onRefresh}>
            刷新
          </Button>
        </div>
        <CardDescription>选择一个会议作为运行入口。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ScrollArea className="h-[260px] rounded-xl border bg-background/60 p-2">
          <div className="space-y-2">
            {meetings.map((meeting) => {
              const meta = extractMeetingMeta(meeting)
              const title = meeting.title || meta.topic || "未命名会议"
              const active = meeting.id === selectedId
              return (
                <button
                  key={meeting.id}
                  type="button"
                  onClick={() => onSelect(meeting.id)}
                  className={`w-full rounded-lg border px-3 py-2 text-left text-xs transition ${
                    active
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border/70 bg-card/80 text-foreground"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 text-sm font-semibold">
                    <span className="line-clamp-1">{title}</span>
                    <Badge variant="secondary">#{shortId(meeting.id, 4)}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {clampText(meta.topic || "未填写议题", 48)}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                    <span>创建：{formatTimestamp(meeting.created_at)}</span>
                    {meta.maxRounds !== undefined && <span>轮次：{meta.maxRounds}</span>}
                    {meta.contextMode && <span>上下文：{meta.contextMode}</span>}
                    {meta.parallelMode !== undefined && (
                      <span>{meta.parallelMode ? "并行" : "串行"}</span>
                    )}
                  </div>
                  {meta.roles.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {meta.roles.slice(0, 5).map((role) => (
                        <Badge key={role} variant="outline" className="text-[10px]">
                          {role}
                        </Badge>
                      ))}
                      {meta.roles.length > 5 && (
                        <Badge variant="outline" className="text-[10px]">
                          +{meta.roles.length - 5}
                        </Badge>
                      )}
                    </div>
                  )}
                </button>
              )
            })}
            {!meetings.length && (
              <div className="rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">
                暂无会议，请先创建一条会议配置。
              </div>
            )}
          </div>
        </ScrollArea>

        <Separator />

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold">创建会议</div>
            <Button variant="ghost" size="sm" onClick={onResetTemplate}>
              重置模板
            </Button>
          </div>
          <div className="text-xs text-muted-foreground">JSON 配置</div>
          <Textarea
            value={draftConfig}
            onChange={(event) => onDraftChange(event.target.value)}
            spellCheck={false}
          />
          {createError && <div className="text-xs text-destructive">{createError}</div>}
          <Button className="w-full" onClick={onCreate} disabled={isCreating}>
            {isCreating ? "创建中..." : "创建会议"}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
