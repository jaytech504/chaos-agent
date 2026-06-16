"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Play, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Session {
  id: string;
  appName: string;
  appUrl: string;
  status: string;
  endpointsTested: number;
  failuresFound: number;
  fixesGenerated: number;
  date: string;
}

const MOCK_SESSIONS: Session[] = [
  {
    id: "scan-1",
    appName: "payments-api",
    appUrl: "https://api.acme.com/v1/payments",
    status: "complete",
    endpointsTested: 14,
    failuresFound: 8,
    fixesGenerated: 3,
    date: "2 hours ago",
  },
  {
    id: "scan-2",
    appName: "user-service",
    appUrl: "https://api.acme.com/v1/users",
    status: "complete",
    endpointsTested: 9,
    failuresFound: 3,
    fixesGenerated: 1,
    date: "5 hours ago",
  },
  {
    id: "scan-3",
    appName: "notification-api",
    appUrl: "https://api.acme.com/v1/notify",
    status: "running",
    endpointsTested: 6,
    failuresFound: 0,
    fixesGenerated: 0,
    date: "Just now",
  },
];

export default function DashboardPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSessions = async () => {
      const token = localStorage.getItem("patchflow_token");
      try {
        const response = await fetch("http://localhost:8000/api/sessions", {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (response.ok) {
          const data = await response.json();
          const mapped = data.map((s: any) => ({
            id: s.id,
            appName: s.target_name || "My API",
            appUrl: s.target_url || "",
            status: s.status,
            endpointsTested: s.endpoints_found || 0,
            failuresFound: s.failures_injected || 0,
            fixesGenerated: s.fixes_generated || 0,
            date: s.created_at ? new Date(s.created_at).toLocaleDateString() : "unknown",
          }));
          setSessions(mapped);
        } else {
          throw new Error("Failed to fetch sessions");
        }
      } catch (err) {
        console.warn("Could not fetch sessions from backend, loading fallback mocks.", err);
        setSessions(MOCK_SESSIONS);
      } finally {
        setLoading(false);
      }
    };

    fetchSessions();
  }, []);

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === "complete" || s === "completed") {
      return (
        <Badge className="bg-emerald-500 hover:bg-emerald-600 text-white flex items-center gap-1">
          <CheckCircle2 className="h-3 w-3" />
          <span>Complete</span>
        </Badge>
      );
    }
    if (s === "failed") {
      return (
        <Badge className="bg-destructive hover:bg-destructive/90 text-white flex items-center gap-1">
          <XCircle className="h-3 w-3" />
          <span>Failed</span>
        </Badge>
      );
    }
    // Any other state (pending, discovering, injecting, analysing, fixing, opening_prs) is running
    return (
      <Badge className="bg-blue-500 hover:bg-blue-600 text-white flex items-center gap-1 animate-pulse">
        <Loader2 className="h-3 w-3 animate-spin" />
        <span>{status.charAt(0).toUpperCase() + status.slice(1)}</span>
      </Badge>
    );
  };

  return (
    <div className="mx-auto max-w-7xl px-6 py-12 w-full flex flex-col bg-white min-h-[calc(100vh-4rem)]">
      {/* Top Section */}
      <div className="flex items-center justify-between pb-8 border-b border-zinc-100">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-900">Dashboard</h1>
          <p className="text-sm text-zinc-500 mt-1">
            API reliability testing reports and active sessions.
          </p>
        </div>

        <Link
          href="/sessions/new"
          className={cn(buttonVariants({ size: "lg" }), "flex items-center gap-2 font-medium")}
        >
          <Plus className="h-4.5 w-4.5" />
          <span>Run New Test</span>
        </Link>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
          <p className="text-sm text-zinc-400">Loading your test reports...</p>
        </div>
      ) : (
        <div className="mt-8 flex flex-col gap-4">
          {sessions.length === 0 ? (
            <div className="text-center py-20 border border-dashed rounded-xl bg-zinc-50/50">
              <p className="text-sm text-zinc-400">No test runs found. Click "Run New Test" to get started.</p>
            </div>
          ) : (
            sessions.map((session) => {
              const s = session.status.toLowerCase();
              const isRunning = !["complete", "completed", "failed"].includes(s);
              const linkTarget = isRunning
                ? `/sessions/${session.id}`
                : `/sessions/${session.id}/report`;

              return (
                <Link
                  key={session.id}
                  href={linkTarget}
                  className="flex flex-col sm:flex-row sm:items-center justify-between p-6 bg-white border border-zinc-200 rounded-xl hover:border-zinc-400 transition-all hover:shadow-sm cursor-pointer group gap-6"
                >
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-3">
                      <span className="font-bold text-lg text-zinc-900 group-hover:text-primary transition-colors">
                        {session.appName}
                      </span>
                      {getStatusBadge(session.status)}
                    </div>
                    <span className="text-sm text-zinc-500 font-mono">
                      {session.appUrl}
                    </span>
                  </div>

                  {/* Stats Row */}
                  <div className="flex flex-wrap items-center gap-8 sm:gap-12">
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                        Endpoints Tested
                      </span>
                      <span className="text-lg font-bold text-zinc-800 mt-1">
                        {session.endpointsTested}
                      </span>
                    </div>

                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                        Failures Found
                      </span>
                      <span className={cn(
                        "text-lg font-bold mt-1",
                        session.failuresFound > 0 && s !== "failed" ? "text-destructive" : "text-zinc-800"
                      )}>
                        {s === "failed" ? "-" : session.failuresFound}
                      </span>
                    </div>

                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                        Fixes Generated
                      </span>
                      <span className={cn(
                        "text-lg font-bold mt-1",
                        session.fixesGenerated > 0 ? "text-primary" : "text-zinc-800"
                      )}>
                        {s === "failed" ? "-" : session.fixesGenerated}
                      </span>
                    </div>

                    <div className="flex flex-col text-right sm:min-w-[100px] justify-center">
                      <span className="text-xs text-zinc-400">{session.date}</span>
                    </div>
                  </div>
                </Link>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
