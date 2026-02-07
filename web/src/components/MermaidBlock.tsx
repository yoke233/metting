import * as React from "react"
import mermaid from "mermaid"

type MermaidBlockProps = {
  code: string
}

let mermaidInitialized = false

export function MermaidBlock({ code }: MermaidBlockProps) {
  const [svg, setSvg] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)
  const id = React.useId()

  React.useEffect(() => {
    // Initialize mermaid only once per session to keep rendering stable.
    if (!mermaidInitialized) {
      mermaid.initialize({ startOnLoad: false, theme: "neutral" })
      mermaidInitialized = true
    }
  }, [])

  React.useEffect(() => {
    // Render the diagram on code changes.
    let active = true
    setError(null)
    mermaid
      .render(`mermaid-${id}`, code)
      .then((result) => {
        if (!active) return
        setSvg(result.svg ?? "")
      })
      .catch((err) => {
        if (!active) return
        setError(err instanceof Error ? err.message : "渲染失败")
        setSvg("")
      })
    return () => {
      active = false
    }
  }, [code, id])

  if (error) {
    return <pre className="text-sm text-destructive">{error}</pre>
  }

  return (
    <div
      className="rounded-xl border bg-card p-4 shadow-sm"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
