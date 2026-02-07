import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { clampText } from "@/lib/format"
import type { ArtifactSummary } from "@/lib/types"

type SummariesPanelProps = {
  summaries: ArtifactSummary[]
}

function toDisplayText(value: unknown) {
  // toDisplayText: normalize list items for rendering.
  if (value === null || value === undefined) return ""
  if (typeof value === "string") return value
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function renderList(items: unknown) {
  // renderList: display array values in a compact list.
  if (!Array.isArray(items) || items.length === 0) {
    return <div className="text-sm text-muted-foreground">无</div>
  }
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
      {items.map((item, index) => (
        <li key={`${toDisplayText(item)}-${index}`}>{clampText(toDisplayText(item), 120)}</li>
      ))}
    </ul>
  )
}

// SummariesPanel: display per-round summaries.
export function SummariesPanel({ summaries }: SummariesPanelProps) {
  return (
    <Card className="border-muted/60 bg-card/80 shadow-lg">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg">轮次摘要</CardTitle>
        <Badge variant="secondary">{summaries.length} 条</Badge>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[380px] pr-2">
          <div className="space-y-3">
            {summaries.map((summary) => {
              const payload = summary.content ?? {}
              const round = (payload as { round?: number }).round
              const text =
                (payload as { summary?: string }).summary ?? (payload as { text?: string }).text
              return (
                <div
                  key={`${summary.run_id}-${summary.created_ts_ms}`}
                  className="rounded-lg border p-3 text-[13px]"
                >
                  <div className="flex items-center justify-between gap-2 text-base font-semibold">
                    <span>第 {round ?? "?"} 轮</span>
                    <Badge variant="outline">{summary.version}</Badge>
                  </div>
                  <div className="mt-2 text-sm text-muted-foreground">
                    {text ? clampText(String(text), 200) : "无摘要内容"}
                  </div>
                  <div className="mt-3 grid gap-2 text-sm">
                    <div>
                      <div className="font-semibold">决策</div>
                      {renderList((payload as { decisions?: unknown }).decisions)}
                    </div>
                    <div>
                      <div className="font-semibold">开放问题</div>
                      {renderList((payload as { open_questions?: unknown }).open_questions)}
                    </div>
                    <div>
                      <div className="font-semibold">风险</div>
                      {renderList((payload as { risks?: unknown }).risks)}
                    </div>
                    <div>
                      <div className="font-semibold">下一步</div>
                      {renderList((payload as { next_steps?: unknown }).next_steps)}
                    </div>
                  </div>
                </div>
              )
            })}
            {!summaries.length && (
              <div className="rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">
                暂无摘要信息。
              </div>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
