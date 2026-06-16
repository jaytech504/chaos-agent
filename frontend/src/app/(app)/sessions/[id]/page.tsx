"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2, ArrowRight, Terminal, Layers } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface LogMessage {
  time: string;
  agent: string;
  type: string;
  content: string;
}

interface TestPill {
  id: string;
  endpoint: string;
  failureMode: string;
  status: "unhandled" | "handled" | "degraded";
  statusCode: number;
  errorLeaked: boolean;
}

const STAGES = ["Discovering", "Injecting", "Analysing", "Fixing", "Opening PRs"];

const MOCK_PILLS_TIMELINE: TestPill[] = [
  { id: "1", endpoint: "GET /users", failureMode: "db_connection_drop", status: "unhandled", statusCode: 500, errorLeaked: true },
  { id: "2", endpoint: "POST /payments/charge", failureMode: "http_429", status: "handled", statusCode: 429, errorLeaked: false },
  { id: "3", endpoint: "GET /inventory", failureMode: "db_timeout", status: "unhandled", statusCode: 500, errorLeaked: true },
  { id: "4", endpoint: "GET /notes", failureMode: "empty_response", status: "degraded", statusCode: 200, errorLeaked: false },
  { id: "5", endpoint: "POST /users", failureMode: "malformed_json", status: "unhandled", statusCode: 400, errorLeaked: true },
  { id: "6", endpoint: "GET /payments/charge", failureMode: "slow_response", status: "handled", statusCode: 200, errorLeaked: false },
  { id: "7", endpoint: "GET /ai/recommend", failureMode: "http_503", status: "degraded", statusCode: 502, errorLeaked: false },
];

export default function LiveSessionPage() {
  const params = useParams();
  const sessionUrlId = params?.id || "mock-id";

  const [activeStage, setActiveStage] = useState(0);
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const [pills, setPills] = useState<TestPill[]>([]);
  const [hoveredPill, setHoveredPill] = useState<TestPill | null>(null);
  const [runFinished, setRunFinished] = useState(false);
  const [loading, setLoading] = useState(true);

  const logsEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Map backend status to stage index
  const getStageIndex = (status: string): number => {
    const s = status.toLowerCase();
    if (s.includes("discover")) return 0;
    if (s.includes("inject")) return 1;
    if (s.includes("analys") || s.includes("analyz")) return 2;
    if (s.includes("fix")) return 3;
    if (s.includes("pr")) return 4;
    return 0;
  };

  useEffect(() => {
    const loadSessionAndConnect = async () => {
      // 1. Fetch initial state from backend API
      try {
        const response = await fetch(`http://localhost:8000/api/sessions/${sessionUrlId}`);
        if (response.ok) {
          const data = await response.json();
          
          // Load past steps
          if (Array.isArray(data.agent_steps)) {
            setLogs(data.agent_steps.map((step: any) => ({
              time: step.created_at ? new Date(step.created_at).toLocaleTimeString() : "",
              agent: step.agent.replace("Agent", ""),
              type: step.step_type,
              content: step.content,
            })));
          }

          // Load past failures
          if (Array.isArray(data.failures)) {
            setPills(data.failures.map((f: any) => ({
              id: f.id,
              endpoint: f.endpoint_id, // fallback endpoint ID
              failureMode: f.failure_mode,
              status: f.result,
              statusCode: f.status_code,
              errorLeaked: f.error_leaked,
            })));
          }

          // Set active stage status
          const stageIdx = getStageIndex(data.status);
          setActiveStage(stageIdx);

          if (["complete", "completed", "failed"].includes(data.status.toLowerCase())) {
            setRunFinished(true);
          }
        }
      } catch (err) {
        console.warn("Failed to load initial session state, using simulated socket stream.", err);
        // If API fails (e.g. mock-id), we can trigger dummy timeline simulation to make UI alive
        simulateMocks();
      } finally {
        setLoading(false);
      }

      // 2. Connect to WebSocket stream
      const wsUrl = `ws://localhost:8000/ws/${sessionUrlId}`;
      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        console.log(`WS connection opened for session ${sessionUrlId}`);
      };

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const type = msg.type;
          const payload = msg.payload;

          if (type === "agent_step") {
            setLogs((prev) => [
              ...prev,
              {
                time: new Date().toLocaleTimeString(),
                agent: payload.agent.replace("Agent", ""),
                type: payload.step_type,
                content: payload.content,
              },
            ]);
          } else if (type === "failure_result") {
            const newPill: TestPill = {
              id: payload.id,
              endpoint: payload.endpoint_id,
              failureMode: payload.failure_mode,
              status: payload.result,
              statusCode: payload.status_code,
              errorLeaked: payload.error_leaked,
            };
            setPills((prev) => {
              // Update if exists, otherwise append
              const idx = prev.findIndex((p) => p.id === newPill.id);
              if (idx > -1) {
                const updated = [...prev];
                updated[idx] = newPill;
                return updated;
              }
              return [...prev, newPill];
            });
          } else if (type === "status") {
            const stageIdx = getStageIndex(payload.status);
            setActiveStage(stageIdx);
            if (["complete", "completed", "failed"].includes(payload.status.toLowerCase())) {
              setRunFinished(true);
            }
          } else if (type === "report_ready") {
            setRunFinished(true);
          }
        } catch (e) {
          console.error("Error parsing WebSocket message:", e);
        }
      };

      socket.onerror = (err) => {
        console.error("WebSocket error:", err);
      };

      socket.onclose = () => {
        console.log("WebSocket connection closed");
      };
    };

    const simulateMocks = () => {
      // Simulate slow logs for mock demo sessions
      const timer = setTimeout(() => {
        setLogs([
          { time: "13:04:15", agent: "Discovery", type: "thinking", content: "Locating endpoints on targets URL https://api.acme.com/v1" },
          { time: "13:04:16", agent: "Discovery", type: "calling_tool", content: "Fetching OpenAPI catalog definitions..." },
          { time: "13:04:17", agent: "Discovery", type: "result", content: "Endpoints cataloged: 14 target routes identified" },
        ]);
        setPills(MOCK_PILLS_TIMELINE);
        setActiveStage(4);
        setRunFinished(true);
      }, 500);
      return () => clearTimeout(timer);
    };

    loadSessionAndConnect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [sessionUrlId]);

  const getAgentColor = (agent: string) => {
    switch (agent) {
      case "Discovery":
        return "text-blue-400";
      case "Chaos":
        return "text-purple-400";
      case "Analyst":
        return "text-amber-400";
      case "Fix":
        return "text-emerald-400";
      case "GitHub":
        return "text-sky-400";
      default:
        return "text-zinc-400";
    }
  };

  const getLogTypeColor = (type: string) => {
    switch (type) {
      case "thinking":
        return "text-zinc-500 italic";
      case "calling_tool":
      case "tool_call":
        return "text-zinc-400";
      case "result":
      case "observation":
        return "text-zinc-200 font-medium";
      default:
        return "text-zinc-300";
    }
  };

  const getPillBg = (status: TestPill["status"]) => {
    switch (status) {
      case "unhandled":
        return "bg-red-500 border-red-600 hover:bg-red-600 text-white";
      case "handled":
        return "bg-emerald-500 border-emerald-600 hover:bg-emerald-600 text-white";
      case "degraded":
        return "bg-amber-500 border-amber-600 hover:bg-amber-600 text-white";
      default:
        return "bg-zinc-200 border-zinc-300 text-zinc-600";
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 w-full flex flex-col gap-6 bg-white min-h-[calc(100vh-4rem)]">
      {/* Title */}
      <div className="flex items-center justify-between border-b border-zinc-100 pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-zinc-900">
            Scanning session target
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            Live failure injection scanning and PR generation pipeline.
          </p>
        </div>

        {runFinished && (
          <Link
            href={`/sessions/${sessionUrlId}/report`}
            className={cn(buttonVariants({ size: "lg" }), "flex items-center gap-2 animate-fade-in font-medium")}
          >
            <span>View Report</span>
            <ArrowRight className="h-4.5 w-4.5" />
          </Link>
        )}
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4 flex-1">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
          <p className="text-sm text-zinc-400 font-medium">Opening connection stream...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-stretch flex-1">
          {/* Left Panel: Agent Trace (Terminal style) */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-zinc-800">
              <Terminal className="h-4.5 w-4.5 text-zinc-500" />
              <span>Agent Trace</span>
            </div>

            <div className="flex-1 bg-zinc-900 border border-zinc-850 rounded-xl overflow-hidden shadow-inner flex flex-col min-h-[450px]">
              <div className="border-b border-zinc-800 bg-zinc-950 px-4 py-3 flex items-center gap-2 shrink-0">
                <div className="h-3 w-3 rounded-full bg-red-500" />
                <div className="h-3 w-3 rounded-full bg-yellow-500" />
                <div className="h-3 w-3 rounded-full bg-green-500" />
                <span className="text-xs text-zinc-500 font-mono ml-4">agent-workspace-logs.sh</span>
              </div>

              <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-2.5 font-mono text-[11px] leading-relaxed text-zinc-300">
                {logs.length === 0 ? (
                  <span className="text-zinc-500 italic animate-pulse">Establishing stream socket...</span>
                ) : (
                  logs.map((log, index) => (
                    <div key={index} className="flex items-start gap-2.5">
                      <span className="text-zinc-600 shrink-0 select-none">[{log.time}]</span>
                      <span className={cn(getAgentColor(log.agent), "font-bold shrink-0")}>
                        {log.agent}Agent
                      </span>
                      <span className={cn(getLogTypeColor(log.type), "flex-1")}>
                        {log.type === "thinking" && "thought: "}
                        {log.content}
                      </span>
                    </div>
                  ))
                )}
                <div ref={logsEndRef} />
              </div>
            </div>
          </div>

          {/* Right Panel: Results (Status bar + Pills grid) */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-zinc-800">
              <Layers className="h-4.5 w-4.5 text-zinc-500" />
              <span>Scan Results</span>
            </div>

            <div className="flex-1 border border-zinc-200 rounded-xl p-6 flex flex-col gap-6 min-h-[450px] justify-between">
              {/* Stages Status bar */}
              <div className="w-full flex items-center justify-between gap-1">
                {STAGES.map((stage, idx) => {
                  const isActive = idx === activeStage;
                  const isCompleted = idx < activeStage;
                  return (
                    <div key={stage} className="flex-1 flex flex-col gap-1 items-center relative">
                      <div className={cn(
                        "h-1.5 w-full rounded-full transition-colors duration-500",
                        isActive ? "bg-primary animate-pulse" : isCompleted ? "bg-emerald-500" : "bg-zinc-200"
                      )} />
                      <span className={cn(
                        "text-[10px] font-semibold tracking-tight transition-colors duration-500 mt-1",
                        isActive ? "text-primary font-bold" : isCompleted ? "text-emerald-600" : "text-zinc-400"
                      )}>
                        {stage}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Grid of Pills */}
              <div className="flex-1 border border-zinc-100 rounded-lg p-6 bg-zinc-50/50 mt-4 flex flex-col justify-between min-h-[250px]">
                <div>
                  <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-4">
                    Injected failure modes ({pills.length} run)
                  </h4>

                  <div className="flex flex-wrap gap-2.5">
                    {pills.length === 0 ? (
                      <span className="text-xs text-zinc-400 italic">Waiting for discovery...</span>
                    ) : (
                      pills.map((pill) => (
                        <div
                          key={pill.id}
                          onMouseEnter={() => setHoveredPill(pill)}
                          onMouseLeave={() => setHoveredPill(null)}
                          className={cn(
                            "px-3 py-1.5 rounded-full text-xs font-medium border cursor-help select-none shadow-sm transition-all hover:scale-105 duration-200",
                            getPillBg(pill.status)
                          )}
                        >
                          {pill.failureMode}
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Hover Tooltip display box */}
                <div className="border-t border-zinc-200 pt-4 mt-6 min-h-[85px] flex items-center justify-center">
                  {hoveredPill ? (
                    <div className="w-full text-left flex flex-col gap-1.5 animate-fade-in">
                      <div className="flex items-center justify-between gap-4">
                        <span className="font-bold text-sm text-zinc-900">{hoveredPill.endpoint}</span>
                        <span className={cn(
                          "text-xs font-bold px-2 py-0.5 rounded border",
                          hoveredPill.status === "unhandled" ? "bg-red-50 text-red-700 border-red-200" :
                          hoveredPill.status === "handled" ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                          "bg-amber-50 text-amber-700 border-amber-200"
                        )}>
                          {hoveredPill.status.toUpperCase()} &middot; {hoveredPill.statusCode}
                        </span>
                      </div>
                      <div className="text-xs text-zinc-500 leading-relaxed">
                        Tested with <span className="font-mono text-zinc-800">{hoveredPill.failureMode}</span>.
                        {hoveredPill.errorLeaked ? (
                          <span className="text-red-600 font-medium ml-1">Error trace details leaked in response.</span>
                        ) : (
                          <span className="text-zinc-500 ml-1">Endpoint responded safely within timeout thresholds.</span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <span className="text-xs text-zinc-400 italic">Hover a failure pill above to view details</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
