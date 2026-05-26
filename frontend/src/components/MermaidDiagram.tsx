import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  theme: "dark",
  themeVariables: {
    background: "#111827",
    primaryColor: "#6366f1",
    primaryTextColor: "#f3f4f6",
    lineColor: "#4b5563",
    edgeLabelBackground: "#1f2937",
  },
});

interface MermaidDiagramProps {
  title: string;
  source: string;
}

let _idCounter = 0;

export default function MermaidDiagram({ title, source }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const idRef = useRef(`mermaid-${++_idCounter}`);

  useEffect(() => {
    if (!source || !containerRef.current) return;
    setError(null);

    console.log("[MermaidDiagram] Rendering diagram:", title, "length:", source.length);

    mermaid.render(idRef.current, source)
      .then(({ svg }) => {
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      })
      .catch((err) => {
        console.error("[MermaidDiagram] Render error for", title, ":", err);
        setError(`Failed to render diagram: ${err.message ?? err}`);
      });
  }, [source, title]);

  const handleCopy = () => {
    navigator.clipboard.writeText(source).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (!source) {
    return (
      <div className="rounded-lg border border-canvas-800 bg-canvas-900 p-6 text-center text-canvas-600 text-sm">
        {title} — not yet generated
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-canvas-800 bg-canvas-900 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-canvas-800">
        <span className="text-sm font-medium text-canvas-300">{title}</span>
        <button
          onClick={handleCopy}
          className="text-xs text-canvas-500 hover:text-canvas-300 transition-colors px-2 py-1 rounded hover:bg-canvas-800"
        >
          {copied ? "✓ Copied" : "Copy Mermaid Source"}
        </button>
      </div>

      {error ? (
        <div className="p-4 text-red-400 text-xs font-mono">{error}</div>
      ) : (
        <div
          ref={containerRef}
          className="p-4 overflow-x-auto flex justify-center [&>svg]:max-w-full"
        />
      )}
    </div>
  );
}
