import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { formatTimestamp, shortId } from "@/lib/format"
import type { Run } from "@/lib/types"

type RunsPanelProps = {
  runs: Run[]
  selectedId: string | null
  onSelect: (id: string) => void
  onRefresh: () => void
}

function statusBadge(status: string) {
  // statusBadge: map run status to visual treatment.
  if (status === "DONE") return <Badge variant="secondary">已完成</Badge>
  if (status === "FAILED") return <Badge variant="destructive">失败</Badge>
  if (status === "PAUSED") return <Badge variant="outline">暂停</Badge>
  return <Badge>运行中</Badge>
}

// RunsPanel: list runs for selection.
export function RunsPanel({ runs, selectedId, onSelect, onRefresh }: RunsPanelProps) {
  return (
    <Card className="border-muted/60 bg-card/80 shadow-lg">
      <CardHeader className="gap-2">
        <div className="flex items-center justify-between gap-4">
          <CardTitle className="text-lg">运行记录</CardTitle>
          <Button variant="outline" size="sm" onClick={onRefresh}>
            刷新
          </Button>
        </div>
        <CardDescription>选择一条 run 查看事件与摘要。</CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[220px] rounded-xl border bg-background/60 p-2">
          <div className="space-y-2">
            {runs.map((run) => {
              const active = run.id === selectedId
              return (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => onSelect(run.id)}
                  className={`w-full rounded-lg border px-3 py-2 text-left text-xs transition ${
                    active
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border/70 bg-card/80 text-foreground"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 text-sm font-semibold">
                    <span>Run #{shortId(run.id, 5)}</span>
                    {statusBadge(run.status)}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                    <span>开始：{formatTimestamp(run.started_at)}</span>
                    <span>结束：{formatTimestamp(run.ended_at)}</span>
                  </div>
                </button>
              )
            })}
            {!runs.length && (
              <div className="rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">
                暂无运行记录。
              </div>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
