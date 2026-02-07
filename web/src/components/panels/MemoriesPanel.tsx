import * as React from "react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { clampText, formatTimestamp } from "@/lib/format"
import type { MemorySnapshot } from "@/lib/types"

type MemoriesPanelProps = {
  memories: MemorySnapshot[]
  selectedRole: string | null
  onSelectRole: (role: string) => void
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

function renderMemoryList(items: unknown) {
  // renderMemoryList: normalize array sections to bullet lists.
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

// MemoriesPanel: display per-role memory snapshots.
export function MemoriesPanel({ memories, selectedRole, onSelectRole }: MemoriesPanelProps) {
  const selected = React.useMemo(
    () => memories.find((item) => item.role_name === selectedRole) ?? memories[0],
    [memories, selectedRole]
  )

  return (
    <Card className="border-muted/60 bg-card/80 shadow-lg">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg">角色记忆</CardTitle>
        <Badge variant="secondary">{memories.length} 个</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <Select
          value={selected?.role_name ?? ""}
          onValueChange={(value) => value && onSelectRole(value)}
        >
          <SelectTrigger>
            <SelectValue placeholder="选择角色" />
          </SelectTrigger>
          <SelectContent>
            {memories.map((memory) => (
              <SelectItem key={memory.role_name} value={memory.role_name}>
                {memory.role_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <ScrollArea className="h-[380px] rounded-xl border bg-background/60 p-3 text-[13px]">
          {selected ? (
            <div className="space-y-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{selected.role_name}</Badge>
                <span className="text-muted-foreground">
                  更新：{formatTimestamp(selected.updated_ts_ms)}
                </span>
              </div>
              <div>
                <div className="font-semibold">假设</div>
                {renderMemoryList((selected.content as { assumptions?: unknown }).assumptions)}
              </div>
              <div>
                <div className="font-semibold">待确认</div>
                {renderMemoryList((selected.content as { pending_checks?: unknown }).pending_checks)}
              </div>
              <div>
                <div className="font-semibold">风险池</div>
                {renderMemoryList((selected.content as { risks_pool?: unknown }).risks_pool)}
              </div>
              <div>
                <div className="font-semibold">决策/笔记</div>
                {renderMemoryList((selected.content as { notes?: unknown }).notes)}
              </div>
              <div>
                <div className="font-semibold">草案</div>
                {renderMemoryList((selected.content as { drafts?: unknown }).drafts)}
              </div>
            </div>
          ) : (
            <div className="text-center text-xs text-muted-foreground">暂无记忆数据。</div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
