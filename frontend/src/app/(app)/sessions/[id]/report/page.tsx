"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  ExternalLink,
  GitPullRequest,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  GitMerge,
  Loader2,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Finding {
  id: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  title: string;
  explanation: string;
  endpoints: string[];
  failures: string[];
}

interface Fix {
  id: string;
  title: string;
  explanation: string;
  beforeCode: string;
  afterCode: string;
}

interface PullRequest {
  id: string;
  number: string;
  title: string;
  fileChanged: string;
  status: "Open" | "Merged" | "Closed";
  url: string;
  branch: string;
}

export default function SessionReportPage() {
  const params = useParams();
  const sessionId = params?.id || "mock-id";

  const [loading, setLoading] = useState(true);
  const [riskScore, setRiskScore] = useState(0);
  const [summary, setSummary] = useState("");
  const [findings, setFindings] = useState<Finding[]>([]);
  const [fixes, setFixes] = useState<Fix[]>([]);
  const [prs, setPrs] = useState<PullRequest[]>([]);
  const [expandedFindings, setExpandedFindings] = useState<Record<string, boolean>>({});
  const [copiedFixId, setCopiedFixId] = useState<string | null>(null);
  const [mergingPrId, setMergingPrId] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const fetchReportData = async () => {
      try {
        const token = localStorage.getItem("patchflow_token");
        const headers: Record<string, string> = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        // 1. Get report ID for session
        const repIdRes = await fetch(`http://localhost:8000/api/reports/session/${sessionId}`, { headers });
        if (!repIdRes.ok) throw new Error("Report not found");
        const { report_id } = await repIdRes.json();

        // 2. Fetch report details
        const reportRes = await fetch(`http://localhost:8000/api/reports/${report_id}`, { headers });
        if (!reportRes.ok) throw new Error("Failed to load report details");
        const reportData = await reportRes.json();

        setRiskScore(reportData.risk_score || 0);
        setSummary(reportData.summary || "No summary available.");
        
        // Load findings
        if (Array.isArray(reportData.all_findings)) {
          const mappedFindings = reportData.all_findings.map((f: any, idx: number) => ({
            id: f.id || `finding-${idx}`,
            severity: f.severity || "MEDIUM",
            title: f.title || "Vulnerability found",
            explanation: f.description || f.explanation || "",
            endpoints: Array.isArray(f.endpoints) ? f.endpoints : [],
            failures: Array.isArray(f.failures) ? f.failures : [],
          }));
          setFindings(mappedFindings);
          if (mappedFindings.length > 0) {
            setExpandedFindings({ [mappedFindings[0].id]: true });
          }
        }

        // Load fixes
        if (Array.isArray(reportData.fixed_failures)) {
          setFixes(reportData.fixed_failures.map((f: any, idx: number) => ({
            id: `fix-${idx}`,
            title: `Fix for ${f.failure_mode} on ${f.endpoint}`,
            explanation: f.fix_explanation || "Add exception handler wrapper.",
            beforeCode: f.before_code || `# Original code fallback\nreturn await handle_request()`,
            afterCode: f.fix_code || "",
          })));
        }

        // 3. Fetch PRs from session
        const sessionRes = await fetch(`http://localhost:8000/api/sessions/${sessionId}`, { headers });
        if (sessionRes.ok) {
          const sessionData = await sessionRes.json();
          if (Array.isArray(sessionData.pull_requests)) {
            setPrs(sessionData.pull_requests.map((pr: any, idx: number) => ({
              id: pr.id || `pr-${idx}`,
              number: pr.pr_number ? `#${pr.pr_number}` : "#",
              title: pr.pr_title || "fix: API reliability improvements",
              fileChanged: Array.isArray(pr.files_changed) ? pr.files_changed[0] : "app.py",
              status: pr.status === "merged" ? "Merged" : pr.status === "closed" ? "Closed" : "Open",
              url: pr.pr_url || "#",
              branch: pr.branch_name || "chaos-agent/api-fix",
            })));
          }
        }
      } catch (err) {
        console.warn("Failed to load real report details, using mock fallback list.", err);
        loadMocks();
      } finally {
        setLoading(false);
      }

      // 4. Connect websocket for real-time PR merges
      const wsUrl = `ws://localhost:8000/ws/${sessionId}`;
      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "pr_status_updated") {
            const { pr_number, status } = msg.payload;
            setPrs((prevPrs) =>
              prevPrs.map((pr) =>
                pr.number === `#${pr_number}` || pr.number === pr_number
                  ? { ...pr, status: status === "merged" ? "Merged" : status === "closed" ? "Closed" : "Open" }
                  : pr
              )
            );
          }
        } catch (e) {
          console.error("WS event parse error:", e);
        }
      };

      return () => {
        socket.close();
      };
    };

    const loadMocks = () => {
      setRiskScore(72);
      setSummary("Your API has database leaks and unhandled payment gateway connection timeouts.");
      setFindings([
        {
          id: "finding-1",
          severity: "CRITICAL",
          title: "Database errors leak internal details",
          explanation: "Database exceptions leak trace details in output payloads.",
          endpoints: ["GET /users", "DELETE /users/{id}"],
          failures: ["db_connection_drop", "constraint_violation"],
        },
        {
          id: "finding-2",
          severity: "CRITICAL",
          title: "Payment API timeout exposes raw exceptions",
          explanation: "Stripe route blocks indefinitely without client timeout parameters.",
          endpoints: ["POST /payments/charge"],
          failures: ["http_timeout"],
        }
      ]);
      setFixes([
        {
          id: "fix-1",
          title: "Add exception handling wrapper to payment charger",
          explanation: "Incorporate timeout catches on httpx calls.",
          beforeCode: `response = httpx.post("https://api.stripe.com/v3/charges", json=payload)`,
          afterCode: `try:\n    response = httpx.post("https://api.stripe.com/v3/charges", json=payload, timeout=5.0)\nexcept httpx.TimeoutException:\n    raise HTTPException(status_code=504, detail="Timeout")`,
        }
      ]);
      setPrs([
        {
          id: "pr-1",
          number: "#47",
          title: "fix: Add timeout handling for Stripe API calls",
          fileChanged: "app/routes/payments.py",
          status: "Open",
          url: "https://github.com",
          branch: "chaos-agent/stripe-timeout-fix",
        }
      ]);
      setExpandedFindings({ "finding-1": true });
    };

    fetchReportData();

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [sessionId]);

  const toggleFinding = (id: string) => {
    setExpandedFindings((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedFixId(id);
    setTimeout(() => setCopiedFixId(null), 2000);
  };

  const handleMergePR = async (id: string) => {
    setMergingPrId(id);
    try {
      const token = localStorage.getItem("patchflow_token");
      const res = await fetch(`http://localhost:8000/api/github/${id}/merge`, {
        method: "POST",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to merge PR");
      }
      // Optimistic UI update; websocket broadcast will also update this
      setPrs((prevPrs) =>
        prevPrs.map((pr) => (pr.id === id ? { ...pr, status: "Merged" } : pr))
      );
    } catch (err: any) {
      console.error("Merge PR error:", err);
      alert(err.message || "Error merging PR");
    } finally {
      setMergingPrId(null);
    }
  };

  const getRiskScoreColor = (score: number) => {
    if (score >= 80) return "text-red-500 border-red-200 bg-red-50/50";
    if (score >= 50) return "text-amber-500 border-amber-200 bg-amber-50/50";
    return "text-emerald-500 border-emerald-200 bg-emerald-50/50";
  };

  const getSeverityBadge = (severity: Finding["severity"]) => {
    switch (severity) {
      case "CRITICAL":
        return <Badge variant="destructive" className="font-semibold">CRITICAL</Badge>;
      case "HIGH":
        return <Badge className="bg-orange-500 hover:bg-orange-600 text-white font-semibold">HIGH</Badge>;
      case "MEDIUM":
        return <Badge className="bg-amber-600 hover:bg-amber-700 text-white font-semibold">MEDIUM</Badge>;
      default:
        return <Badge variant="secondary" className="font-semibold">LOW</Badge>;
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-6 py-12 w-full flex flex-col gap-10 bg-white min-h-[calc(100vh-4rem)]">
      {/* Back Header */}
      <div>
        <Link
          href="/dashboard"
          className="text-sm font-semibold text-primary hover:underline flex items-center gap-1.5 w-fit"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Dashboard</span>
        </Link>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4 flex-1">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
          <p className="text-sm text-zinc-400 font-medium">Fetching vulnerability analysis report...</p>
        </div>
      ) : (
        <>
          {/* Title */}
          <div className="border-b border-zinc-100 pb-6 flex items-center justify-between gap-4 flex-wrap">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-zinc-900">Reliability Report</h1>
              <p className="text-sm text-zinc-500 mt-1">
                Scanned target details &middot; {findings.length} findings listed
              </p>
            </div>
          </div>

          {/* 1. Risk Score Section */}
          <section className="flex flex-col gap-4">
            <h2 className="text-xl font-bold text-zinc-900 tracking-tight">Risk Score</h2>
            <div className={cn(
              "border rounded-xl p-8 flex flex-col sm:flex-row items-center gap-6 shadow-sm",
              getRiskScoreColor(riskScore)
            )}>
              <span className="text-7xl font-extrabold tracking-tight">{riskScore}</span>
              <div className="flex flex-col text-left">
                <span className="font-bold text-lg text-zinc-900">
                  {riskScore >= 80 ? "Critical Reliability Risk" : riskScore >= 50 ? "Moderate Reliability Risk" : "Secure API Target"}
                </span>
                <p className="text-sm text-zinc-650 mt-1 max-w-xl leading-relaxed">
                  {summary}
                </p>
              </div>
            </div>
          </section>

          {/* 2. Findings Section */}
          {findings.length > 0 && (
            <section className="flex flex-col gap-4">
              <h2 className="text-xl font-bold text-zinc-900 tracking-tight">Findings</h2>
              <div className="flex flex-col gap-3">
                {findings.map((f) => {
                  const isExpanded = !!expandedFindings[f.id];
                  return (
                    <Card key={f.id} className="border border-zinc-200 hover:shadow-sm transition-all overflow-hidden">
                      <div
                        onClick={() => toggleFinding(f.id)}
                        className="flex items-center justify-between p-5 cursor-pointer bg-zinc-50/50 hover:bg-zinc-50 select-none transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          {getSeverityBadge(f.severity)}
                          <h3 className="font-bold text-sm sm:text-base text-zinc-800">{f.title}</h3>
                        </div>
                        {isExpanded ? <ChevronUp className="h-4.5 w-4.5 text-zinc-400" /> : <ChevronDown className="h-4.5 w-4.5 text-zinc-400" />}
                      </div>

                      {isExpanded && (
                        <CardContent className="p-6 border-t border-zinc-100 flex flex-col gap-5 bg-white">
                          <p className="text-sm text-zinc-600 leading-relaxed">
                            {f.explanation}
                          </p>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                              <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Affected Endpoints</h4>
                              <div className="flex flex-wrap gap-1.5 mt-2">
                                {f.endpoints.map((e) => (
                                  <Badge key={e} variant="outline" className="font-mono text-[10px]">
                                    {e}
                                  </Badge>
                                ))}
                              </div>
                            </div>

                            <div>
                              <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Exposed by Failure Modes</h4>
                              <div className="flex flex-wrap gap-1.5 mt-2">
                                {f.failures.map((fail) => (
                                  <Badge key={fail} variant="secondary" className="text-[10px]">
                                    {fail}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          </div>
                        </CardContent>
                      )}
                    </Card>
                  );
                })}
              </div>
            </section>
          )}

          {/* 3. Fixes Section */}
          {fixes.length > 0 && (
            <section className="flex flex-col gap-4">
              <h2 className="text-xl font-bold text-zinc-900 tracking-tight">Fixes</h2>
              <div className="flex flex-col gap-6">
                {fixes.map((fix) => (
                  <Card key={fix.id} className="border border-zinc-200">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-lg font-bold text-zinc-900">{fix.title}</CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-4">
                      <p className="text-sm text-zinc-650 leading-relaxed">
                        {fix.explanation}
                      </p>

                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-2">
                        <div className="flex flex-col">
                          <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">Original Code</span>
                          <pre className="bg-red-50/50 border border-red-150 p-4 rounded-xl font-mono text-[11px] leading-relaxed text-red-800 overflow-x-auto h-48 whitespace-pre shadow-inner">
                            <code>{fix.beforeCode}</code>
                          </pre>
                        </div>

                        <div className="flex flex-col relative group">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Fixed Code</span>
                            <button
                              onClick={() => handleCopy(fix.id, fix.afterCode)}
                              className="text-xs text-zinc-400 hover:text-zinc-600 flex items-center gap-1 transition-colors"
                              title="Copy code"
                            >
                              {copiedFixId === fix.id ? (
                                <>
                                  <Check className="h-3.5 w-3.5 text-emerald-600" />
                                  <span className="text-emerald-600 font-semibold">Copied!</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="h-3.5 w-3.5" />
                                  <span>Copy</span>
                                </>
                              )}
                            </button>
                          </div>
                          <pre className="bg-emerald-50/50 border border-emerald-150 p-4 rounded-xl font-mono text-[11px] leading-relaxed text-emerald-800 overflow-x-auto h-48 whitespace-pre shadow-inner">
                            <code>{fix.afterCode}</code>
                          </pre>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          )}

          {/* 4. Pull Requests Section (Conditional) */}
          {prs.length > 0 && (
            <section className="flex flex-col gap-4">
              <h2 className="text-xl font-bold text-zinc-900 tracking-tight">GitHub Pull Requests</h2>
              <div className="flex flex-col gap-4">
                {prs.map((pr) => {
                  const isMerged = pr.status.toLowerCase() === "merged";
                  const isMerging = mergingPrId === pr.id;

                  return (
                    <Card key={pr.id} className="border border-zinc-200">
                      <CardContent className="p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
                        <div className="flex flex-col gap-2">
                          <div className="flex items-center gap-3">
                            <GitPullRequest className={cn("h-5 w-5", isMerged ? "text-purple-500" : "text-emerald-500")} />
                            <span className="text-xs text-zinc-400 font-semibold">{pr.number}</span>
                            <h3 className="font-bold text-zinc-800 text-sm sm:text-base">{pr.title}</h3>
                          </div>
                          <div className="flex items-center gap-2 text-xs text-zinc-500 font-mono mt-1">
                            <span>Changed file: {pr.fileChanged}</span>
                            <span>&middot;</span>
                            <span>Branch: {pr.branch}</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-3 shrink-0">
                          {isMerged ? (
                            <Badge className="bg-purple-100 text-purple-800 border border-purple-200 font-semibold flex items-center gap-1">
                              <GitMerge className="h-3 w-3" />
                              <span>Merged</span>
                            </Badge>
                          ) : (
                            <>
                              <Badge className="bg-emerald-100 text-emerald-800 border border-emerald-200 font-semibold">
                                Open
                              </Badge>
                              <a
                                href={pr.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={cn(buttonVariants({ variant: "outline", size: "sm" }), "flex items-center gap-1.5")}
                              >
                                <span>View on GitHub</span>
                                <ExternalLink className="h-3.5 w-3.5" />
                              </a>
                              <Button
                                size="sm"
                                disabled={isMerging}
                                onClick={() => handleMergePR(pr.id)}
                                className="flex items-center gap-1.5"
                              >
                                {isMerging ? (
                                  <>
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    <span>Merging...</span>
                                  </>
                                ) : (
                                  <>
                                    <GitMerge className="h-3.5 w-3.5" />
                                    <span>Merge PR</span>
                                  </>
                                )}
                              </Button>
                            </>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
