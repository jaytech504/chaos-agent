"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { Plus, CheckCircle2, XCircle, Activity, AlertTriangle, GitPullRequest, Gauge } from "lucide-react";
import { motion } from "framer-motion";
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

  const stats = useMemo(() => {
    const totalTests = sessions.length;
    const totalFailures = sessions.reduce((sum, s) => sum + s.failuresFound, 0);
    const totalFixes = sessions.reduce((sum, s) => sum + s.fixesGenerated, 0);
    const totalEndpoints = sessions.reduce((sum, s) => sum + s.endpointsTested, 0);
    const avgRiskScore = totalEndpoints > 0 
      ? Math.min(100, Math.round((totalFailures / totalEndpoints) * 100)) 
      : 0;
    
    let scoreColor = "#16A34A";
    if (avgRiskScore >= 30 && avgRiskScore <= 60) scoreColor = "#E04E16";
    else if (avgRiskScore > 60) scoreColor = "#DC2626";

    return { totalTests, totalFailures, totalFixes, avgRiskScore, scoreColor };
  }, [sessions]);

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === "complete" || s === "completed") {
      return (
        <div className="flex items-center gap-1.5 bg-[#F0FDF4] text-[#16A34A] text-[11px] font-[600] px-[10px] py-[4px] rounded-full">
          <CheckCircle2 className="h-3 w-3" />
          <span>Complete</span>
        </div>
      );
    }
    if (s === "failed") {
      return (
        <div className="flex items-center gap-1.5 bg-[#FEF2F2] text-[#DC2626] text-[11px] font-[600] px-[10px] py-[4px] rounded-full">
          <XCircle className="h-3 w-3" />
          <span>Failed</span>
        </div>
      );
    }
    // Any other state (pending, discovering, injecting, analysing, fixing, opening_prs) is running
    return (
      <div className="flex items-center gap-1.5 bg-[#FFEDE3] text-[#E04E16] text-[11px] font-[600] px-[10px] py-[4px] rounded-full">
        <div className="h-1.5 w-1.5 rounded-full bg-[#E04E16] animate-pulse" />
        <span>{status.charAt(0).toUpperCase() + status.slice(1)}</span>
      </div>
    );
  };

  return (
    <div className="mx-auto max-w-5xl px-6 py-12 w-full flex flex-col min-h-screen">
      {/* Page Header */}
      <div className="flex items-center justify-between pb-6 border-b border-[#E7E5E2] mb-[24px]">
        <div>
          <h1 className="text-[32px] font-[800] text-[#111110] leading-none">Dashboard</h1>
          <p className="text-[15px] text-[#6F6B66] mt-2">
            API reliability testing reports and active sessions.
          </p>
        </div>
        <Link
          href="/sessions/new"
          className="bg-[#FF5A1F] hover:bg-[#E04E16] text-white font-[600] rounded-[10px] px-[20px] py-[12px] flex items-center gap-2 transition-all duration-150 hover:-translate-y-[1px] hover:shadow-sm"
        >
          <Plus className="h-4.5 w-4.5" />
          <span>Run New Test</span>
        </Link>
      </div>

      {!loading && sessions.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-[16px] mb-[32px]">
          {/* Card 1 */}
          <motion.div
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: "easeOut", delay: 0.0 }}
            className="bg-white border border-[#E7E5E2] rounded-[14px] p-[20px] hover:border-[#D4D1CC] transition-colors duration-150 flex flex-col"
          >
            <Activity className="h-[18px] w-[18px] text-[#A3A099] mb-4" />
            <span className="text-[24px] font-[800] text-[#111110] leading-none mb-1">{stats.totalTests}</span>
            <span className="text-[13px] text-[#6F6B66]">Total tests run</span>
          </motion.div>

          {/* Card 2 */}
          <motion.div
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: "easeOut", delay: 0.06 }}
            className="bg-white border border-[#E7E5E2] rounded-[14px] p-[20px] hover:border-[#D4D1CC] transition-colors duration-150 flex flex-col"
          >
            <AlertTriangle className="h-[18px] w-[18px] text-[#DC2626] mb-4" />
            <span className="text-[24px] font-[800] text-[#DC2626] leading-none mb-1">{stats.totalFailures}</span>
            <span className="text-[13px] text-[#6F6B66]">Failures found</span>
          </motion.div>

          {/* Card 3 */}
          <motion.div
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: "easeOut", delay: 0.12 }}
            className="bg-white border border-[#E7E5E2] rounded-[14px] p-[20px] hover:border-[#D4D1CC] transition-colors duration-150 flex flex-col"
          >
            <GitPullRequest className="h-[18px] w-[18px] text-[#16A34A] mb-4" />
            <span className="text-[24px] font-[800] text-[#16A34A] leading-none mb-1">{stats.totalFixes}</span>
            <span className="text-[13px] text-[#6F6B66]">Fixes generated</span>
          </motion.div>

          {/* Card 4 */}
          <motion.div
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: "easeOut", delay: 0.18 }}
            className="bg-white border border-[#E7E5E2] rounded-[14px] p-[20px] hover:border-[#D4D1CC] transition-colors duration-150 flex flex-col"
          >
            <Gauge className="h-[18px] w-[18px] text-[#111110] mb-4" />
            <span className="text-[24px] font-[800] leading-none mb-1" style={{ color: stats.scoreColor }}>{stats.avgRiskScore}/100</span>
            <span className="text-[13px] text-[#6F6B66]">Average risk score</span>
          </motion.div>
        </div>
      )}

      {loading ? (
        <div className="flex flex-col gap-[16px]">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-card border border-[#E7E5E2] rounded-[16px] p-[24px]">
              <div className="flex justify-between items-center mb-2">
                <div className="h-5 w-48 bg-[#F3F2F0] animate-pulse rounded" />
                <div className="h-4 w-24 bg-[#F3F2F0] animate-pulse rounded" />
              </div>
              <div className="h-4 w-64 bg-[#F3F2F0] animate-pulse rounded mb-6" />
              <div className="flex gap-[24px]">
                <div className="flex flex-col gap-2">
                  <div className="h-3 w-20 bg-[#F3F2F0] animate-pulse rounded" />
                  <div className="h-6 w-12 bg-[#F3F2F0] animate-pulse rounded" />
                </div>
                <div className="flex flex-col gap-2">
                  <div className="h-3 w-20 bg-[#F3F2F0] animate-pulse rounded" />
                  <div className="h-6 w-12 bg-[#F3F2F0] animate-pulse rounded" />
                </div>
                <div className="flex flex-col gap-2">
                  <div className="h-3 w-20 bg-[#F3F2F0] animate-pulse rounded" />
                  <div className="h-6 w-12 bg-[#F3F2F0] animate-pulse rounded" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : sessions.length === 0 ? (
        <div className="flex flex-col items-center justify-center text-center mt-[120px]">
          <Activity className="h-[48px] w-[48px] text-[#D4D1CC] mb-4" />
          <h2 className="text-[18px] font-[700] text-[#111110] mb-2">No tests yet</h2>
          <p className="text-[14px] text-[#6F6B66] mb-6">Run your first reliability test to find what breaks.</p>
          <Link
            href="/sessions/new"
            className="bg-[#FF5A1F] hover:bg-[#E04E16] text-white font-[600] rounded-[10px] px-[20px] py-[12px] flex items-center gap-2 transition-all duration-150 hover:-translate-y-[1px] hover:shadow-sm"
          >
            <Plus className="h-4.5 w-4.5" />
            <span>Run New Test</span>
          </Link>
        </div>
      ) : (
        <div className="flex flex-col">
          {sessions.map((session, index) => {
            const s = session.status.toLowerCase();
            const isRunning = !["complete", "completed", "failed"].includes(s);
            const linkTarget = isRunning
              ? `/sessions/${session.id}`
              : `/sessions/${session.id}/report`;

            return (
              <motion.div
                key={session.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: "easeOut", delay: (index + 4) * 0.06 }}
                className="mb-[16px]"
              >
                <Link
                  href={linkTarget}
                  className="block bg-card border border-[#E7E5E2] rounded-[16px] p-[24px] hover:border-[#D4D1CC] transition-all duration-150 hover:-translate-y-[1px] hover:shadow-[0_4px_12px_rgba(0,0,0,0.04)]"
                >
                  {/* Row 1 */}
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-3">
                      <span className="text-[17px] font-[700] text-[#111110]">
                        {session.appName}
                      </span>
                      {getStatusBadge(session.status)}
                    </div>
                    <span 
                      className="text-[13px] text-[#A3A099]"
                      title={session.date !== "Just now" && session.date !== "unknown" ? new Date(session.date).toLocaleString() : undefined}
                    >
                      {session.date}
                    </span>
                  </div>

                  {/* Row 2 */}
                  <div className="text-[13px] font-mono text-[#6F6B66] truncate mb-[16px]">
                    {session.appUrl}
                  </div>

                  {/* Row 3 */}
                  <div className="flex items-center gap-[24px]">
                    <div className="flex flex-col">
                      <span className="text-[11px] text-[#A3A099] uppercase tracking-[0.04em] mb-1">
                        Endpoints Tested
                      </span>
                      <span className="text-[22px] font-[700] text-[#111110] leading-none">
                        {session.endpointsTested}
                      </span>
                    </div>

                    <div className="flex flex-col">
                      <span className="text-[11px] text-[#A3A099] uppercase tracking-[0.04em] mb-1">
                        Failures Found
                      </span>
                      <span className={cn(
                        "text-[22px] font-[700] leading-none",
                        session.failuresFound > 0 && s !== "failed" ? "text-[#DC2626]" : "text-[#111110]"
                      )}>
                        {s === "failed" ? "-" : session.failuresFound}
                      </span>
                    </div>

                    <div className="flex flex-col">
                      <span className="text-[11px] text-[#A3A099] uppercase tracking-[0.04em] mb-1">
                        Fixes Generated
                      </span>
                      <span className={cn(
                        "text-[22px] font-[700] leading-none",
                        session.fixesGenerated > 0 && s !== "failed" ? "text-[#16A34A]" : "text-[#111110]"
                      )}>
                        {s === "failed" ? "-" : session.fixesGenerated}
                      </span>
                    </div>
                  </div>
                </Link>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
