import { useState, useCallback, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Cpu, Terminal, ArrowRight } from "lucide-react";
import PipelineProgress, { type StageState } from "../components/PipelineProgress";
import HITLModal from "../components/HITLModal";
import LogViewer from "../components/LogViewer";
import { useSSE } from "../hooks/useSSE";
import type { SSEEvent, HITLRequiredEvent, StageStatus } from "../api/types";

export default function GeneratePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const sessionId = params.get("session");

  const [stages, setStages] = useState<Record<string, StageState>>({});
  const [logEntries, setLogEntries] = useState<string[]>([]);
  const [hitlEvent, setHitlEvent] = useState<HITLRequiredEvent | null>(null);
  const [complete, setComplete] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) navigate("/");
  }, [sessionId, navigate]);

  const handleEvent = useCallback((event: SSEEvent) => {
    console.log("[GeneratePage] SSE:", event.event);

    if (event.event === "stage_update") {
      setStages(prev => ({
        ...prev,
        [event.stage]: {
          status: event.status as StageStatus,
          latencyMs: event.latency_ms,
          tokens: event.tokens_used,
          confidence: event.confidence,
          outputSummary: event.output_summary,
          assumptions: event.assumptions,
          conflicts: event.conflicts,
          repaired: event.status === "repair_triggered" ? true : prev[event.stage]?.repaired,
        },
      }));
      setLogEntries(prev => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ${event.stage} → ${event.status}${event.latency_ms ? ` (${event.latency_ms}ms)` : ""}`,
      ]);
    }

    if (event.event === "hitl_required") {
      setHitlEvent(event);
      setStages(prev => ({ ...prev, [event.stage]: { ...prev[event.stage], status: "hitl_required" } }));
    }

    if (event.event === "log_update") {
      setLogEntries(prev => [...prev, event.content]);
    }

    if (event.event === "pipeline_complete") {
      setComplete(true);
      setLogEntries(prev => [
        ...prev,
        `── Complete in ${event.total_latency_ms}ms · repairs:${event.repair_count} hitl:${event.hitl_count} ──`,
      ]);
    }

    if (event.event === "pipeline_failed") {
      setFailed(event.error);
      setLogEntries(prev => [...prev, `ERROR: ${event.error}`]);
    }
  }, []);

  useSSE({ sessionId, onEvent: handleEvent });

  if (!sessionId) return null;

  return (
    <div className="h-screen bg-canvas-950 bg-noise flex flex-col overflow-hidden">

      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-4 border-b border-canvas-900 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-xl bg-terra-500 flex items-center justify-center shadow-md shadow-terra-500/30">
            <Cpu className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="font-display text-lg text-canvas-100">ProtoFlow</span>
          <span className="text-canvas-700 mx-1 text-sm">/</span>
          <span className="text-xs text-canvas-500">Pipeline</span>
        </div>
        <span className="text-xs text-canvas-700 font-mono truncate max-w-[180px]">{sessionId?.slice(0, 16)}…</span>
      </nav>

      {/* Error banner */}
      {failed && (
        <div className="mx-5 mt-4 px-4 py-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex-shrink-0">
          Pipeline failed: {failed}
        </div>
      )}

      {/* Body — two-panel layout */}
      <div className="flex-1 flex overflow-hidden">

        {/* Left — Pipeline (50%) */}
        <div className="w-1/2 border-r border-canvas-900 overflow-y-auto p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-xs font-semibold text-canvas-500 uppercase tracking-widest">
              Pipeline Stages
            </h2>
            {complete && (
              <button
                onClick={() => navigate(`/results?session=${sessionId}`)}
                className="flex items-center gap-1.5 text-xs font-semibold text-white
                           px-3 py-1.5 rounded-lg bg-terra-500 hover:bg-terra-400 transition-colors"
              >
                View Results <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
          <PipelineProgress stages={stages} complete={complete} onViewResults={() => navigate(`/results?session=${sessionId}`)} />
        </div>

        {/* Right — Log (50%) */}
        <div className="w-1/2 flex flex-col overflow-hidden">
          <div className="flex items-center gap-2.5 px-5 py-3.5 border-b border-canvas-900 flex-shrink-0">
            <Terminal className="w-3.5 h-3.5 text-canvas-600" />
            <span className="text-xs font-semibold text-canvas-600 uppercase tracking-widest">Live Log</span>
          </div>
          <div className="flex-1 overflow-hidden">
            <LogViewer entries={logEntries} />
          </div>
        </div>
      </div>

      {/* HITL Modal */}
      {hitlEvent && (
        <HITLModal
          event={hitlEvent}
          onResume={() => {
            setHitlEvent(null);
            setStages(prev => ({ ...prev, [hitlEvent.stage]: { ...prev[hitlEvent.stage], status: "running" } }));
          }}
        />
      )}
    </div>
  );
}
