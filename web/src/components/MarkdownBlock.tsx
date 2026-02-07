import * as React from "react"
import { marked } from "marked"

type MarkdownBlockProps = {
  text: string
}

export function MarkdownBlock({ text }: MarkdownBlockProps) {
  // Parse markdown once per text change to avoid extra work.
  const html = React.useMemo(() => marked.parse(text), [text])
  return (
    <div
      className="markdown text-sm leading-relaxed"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
