"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  GitPullRequest,
  Copy,
  Check,
  ChevronDown,
  Loader2,
} from "lucide-react";
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
  const [activeSection, setActiveSection] = useState<string>("risk-score");

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
              fileChanged: Array.isArray(pr.files_changed) && pr.files_changed.length > 0 ? pr.files_changed[0] : "app.py",
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

  useEffect(() => {
    if (loading) return;
    const sections = ["risk-score", "findings", "pull-requests", "fixes"];
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        });
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: 0.1 }
    );

    sections.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [loading, findings.length, fixes.length, prs.length]);

  const toggleFinding = (id: string) => {
    setExpandedFindings((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedFixId(id);
    setTimeout(() => setCopiedFixId(null), 1500);
  };

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      const y = el.getBoundingClientRect().top + window.pageYOffset - 120; // Offset for sticky nav
      window.scrollTo({ top: y, behavior: "smooth" });
    }
  };

  const renderHighlightedSummary = (text: string, colorClass: string) => {
    // A simple heuristic to bold some critical phrases (fallback mechanism for mock/demo purposes)
    const criticalPhrases = ["leak internal details", "unhandled payment gateway connection timeouts", "leak trace details", "blocks indefinitely", "raw exceptions"];
    let rendered = text;
    criticalPhrases.forEach((phrase) => {
      const regex = new RegExp(`(${phrase})`, "gi");
      rendered = rendered.replace(regex, `<strong class="${colorClass}">$1</strong>`);
    });
    return <span dangerouslySetInnerHTML={{ __html: rendered }} />;
  };

  const getSeverityPill = (score: number) => {
    if (score > 60) return { label: "HIGH RISK", bg: "bg-[#FEF2F2]", text: "text-[#DC2626]", colorClass: "text-[#DC2626]" };
    if (score >= 30) return { label: "MODERATE RISK", bg: "bg-[#FFEDE3]", text: "text-[#E04E16]", colorClass: "text-[#E04E16]" };
    return { label: "LOW RISK", bg: "bg-[#F0FDF4]", text: "text-[#16A34A]", colorClass: "text-[#16A34A]" };
  };

  const getFindingSeverityBadge = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return "bg-[#FEF2F2] text-[#DC2626]";
      case "HIGH":
        return "bg-[#FFEDE3] text-[#E04E16]";
      case "MEDIUM":
        return "bg-[#FFFBEB] text-[#D97706]";
      default:
        return "bg-[#EFF6FF] text-[#2563EB]";
    }
  };

  const severityPill = getSeverityPill(riskScore);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4 flex-1 min-h-[calc(100vh-4rem)] bg-[#FAFAF9]">
        <Loader2 className="h-8 w-8 text-[#FF5A1F] animate-spin" />
        <p className="text-[14px] text-[#A3A099] font-[500]">Fetching reliability report...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#FAFAF9] flex flex-col w-full">
      <div className="mx-auto max-w-5xl px-6 py-12 w-full flex flex-col">
        {/* Page Header */}
        <div className="pb-6 border-b border-[#E7E5E2] flex flex-col gap-3">
          <Link
            href="/dashboard"
            className="text-[13px] text-[#6F6B66] hover:text-[#111110] transition-colors flex items-center gap-1.5 w-fit"
          >
            <ArrowLeft className="h-[14px] w-[14px]" />
            <span>Dashboard</span>
          </Link>
          <div>
            <h1 className="text-[32px] font-[800] text-[#111110] leading-tight">Reliability Report</h1>
            <p className="text-[14px] text-[#6F6B66] mt-1">
              Scanned target details · {findings.length} findings listed
            </p>
          </div>
        </div>

        {/* Sticky Sub-nav */}
        <div className="sticky top-0 z-40 bg-[#FAFAF9]/80 backdrop-blur-md border-b border-[#E7E5E2] flex items-center gap-6 pt-1 mb-8">
          {["risk-score", "findings", "pull-requests", "fixes"].map((id, index) => {
            const labels = ["Risk Score", "Findings", "Pull Requests", "Fixes"];
            const label = labels[index];
            const isActive = activeSection === id;
            return (
              <button
                key={id}
                onClick={() => scrollToSection(id)}
                className={cn(
                  "py-[12px] text-[13px] font-[500] border-b-[2px] transition-colors",
                  isActive
                    ? "text-[#111110] border-[#FF5A1F]"
                    : "text-[#6F6B66] border-transparent hover:text-[#111110]"
                )}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* Content Sections */}
        <div className="flex flex-col gap-[32px]">
          
          {/* 1. Risk Score Section */}
          <motion.section
            id="risk-score"
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="scroll-mt-[120px]"
          >
            <div className="bg-[#FFFFFF] border border-[#E7E5E2] rounded-[14px] p-[20px] flex flex-col sm:flex-row gap-[20px]">
              <div className="flex flex-col flex-shrink-0">
                <div className="flex items-baseline gap-1">
                  <span className={cn("text-[36px] font-[800] leading-none", severityPill.colorClass)}>
                    {riskScore}
                  </span>
                  <span className="text-[16px] font-[600] text-[#A3A099]">/100</span>
                </div>
                <div className="mt-2">
                  <span className={cn(
                    "text-[11px] font-[700] uppercase tracking-[0.04em] px-[10px] py-[4px] rounded-full inline-block",
                    severityPill.bg,
                    severityPill.text
                  )}>
                    {severityPill.label}
                  </span>
                </div>
              </div>
              <div className="text-[14px] text-[#111110] font-[400] leading-relaxed flex items-center">
                <p>{renderHighlightedSummary(summary, severityPill.colorClass)}</p>
              </div>
            </div>
          </motion.section>

          {/* 2. Findings Section */}
          <motion.section
            id="findings"
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="flex flex-col gap-4 scroll-mt-[120px]"
          >
            <h2 className="text-[18px] font-[700] text-[#111110] tracking-tight mt-[32px]">Findings</h2>
            <div className="flex flex-col gap-3">
              {findings.map((f, i) => {
                const isExpanded = !!expandedFindings[f.id];
                return (
                  <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.35, ease: "easeOut", delay: i * 0.05 }}
                    key={f.id}
                    className="bg-[#FFFFFF] border border-[#E7E5E2] rounded-[14px] hover:border-[#D4D1CC] transition-colors overflow-hidden"
                  >
                    <div
                      onClick={() => toggleFinding(f.id)}
                      className="flex items-center justify-between p-[18px_20px] cursor-pointer select-none"
                    >
                      <div className="flex items-center gap-3">
                        <span className={cn(
                          "text-[11px] font-[700] uppercase px-[10px] py-[4px] rounded-full",
                          getFindingSeverityBadge(f.severity)
                        )}>
                          {f.severity}
                        </span>
                        <h3 className="font-[600] text-[15px] text-[#111110]">{f.title}</h3>
                      </div>
                      <ChevronDown
                        className={cn(
                          "h-[18px] w-[18px] text-[#A3A099] transition-transform duration-300",
                          isExpanded ? "rotate-180" : "rotate-0"
                        )}
                      />
                    </div>

                    <AnimatePresence initial={false}>
                      {isExpanded && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.3, ease: "easeInOut" }}
                          className="overflow-hidden"
                        >
                          <div className="p-[0_20px_20px_20px] flex flex-col gap-4 border-t border-transparent">
                            <div className="pt-2">
                              <p className="text-[14px] text-[#6F6B66] leading-relaxed">
                                {f.explanation}
                              </p>
                            </div>
                            <div className="flex flex-col gap-1.5">
                              <span className="text-[11px] font-[700] text-[#A3A099] uppercase tracking-[0.04em]">Affected Endpoints</span>
                              <div className="flex flex-wrap gap-2">
                                {f.endpoints.map((e) => (
                                  <span key={e} className="bg-[#F8FAFC] border border-[#E2E8F0] text-[12px] font-mono px-[8px] py-[2px] rounded-[6px] text-[#111110]">
                                    {e}
                                  </span>
                                ))}
                              </div>
                            </div>
                            <div className="flex flex-col gap-1.5">
                              <span className="text-[11px] font-[700] text-[#A3A099] uppercase tracking-[0.04em]">Failure Modes</span>
                              <div className="flex flex-wrap items-center gap-2 text-[13px] text-[#111110]">
                                {f.failures.map((fail, idx) => (
                                  <div key={fail} className="flex items-center gap-2">
                                    <span>{fail}</span>
                                    {idx < f.failures.length - 1 && <span className="text-[#D4D1CC]">&middot;</span>}
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                );
              })}
            </div>
          </motion.section>

          {/* 3. Pull Requests Section */}
          <motion.section
            id="pull-requests"
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="flex flex-col gap-4 scroll-mt-[120px]"
          >
            <h2 className="text-[18px] font-[700] text-[#111110] tracking-tight mt-[16px]">Pull Requests</h2>
            <div className="flex flex-col gap-3">
              {prs.length === 0 && (
                <p className="text-[14px] text-[#A3A099]">No pull requests generated yet.</p>
              )}
              {prs.map((pr, i) => {
                let badgeStyle = "bg-[#F3F2F0] text-[#6F6B66]"; // Closed
                if (pr.status === "Merged") badgeStyle = "bg-[#F3E8FF] text-[#7E22CE]";
                if (pr.status === "Open") badgeStyle = "bg-[#FFEDE3] text-[#E04E16]";

                return (
                  <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.35, ease: "easeOut", delay: i * 0.05 }}
                    key={pr.id}
                    className="bg-[#FFFFFF] border border-[#E7E5E2] rounded-[14px] p-[20px] hover:border-[#D4D1CC] transition-colors flex flex-col gap-3"
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex items-center gap-2">
                        <GitPullRequest className={cn("h-[16px] w-[16px]", pr.status === "Merged" ? "text-[#7E22CE]" : "text-[#111110]")} />
                        <span className="text-[15px] font-[600] text-[#111110]">
                          {pr.number} {pr.title}
                        </span>
                      </div>
                      <span className={cn("text-[11px] font-[700] uppercase px-[10px] py-[4px] rounded-full", badgeStyle)}>
                        {pr.status}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-[13px] text-[#A3A099]">
                      <div>
                        <span>Changed file: </span>
                        <span className="font-mono text-[#6F6B66]">{pr.fileChanged}</span>
                        <span className="mx-2">&middot;</span>
                        <span>Branch: </span>
                        <span className="font-mono text-[#6F6B66]">{pr.branch}</span>
                      </div>
                      <a
                        href={pr.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[13px] text-[#E04E16] hover:text-[#FF5A1F] transition-colors"
                      >
                        View on GitHub &rarr;
                      </a>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </motion.section>

          {/* 4. Fixes Section */}
          <motion.section
            id="fixes"
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="flex flex-col gap-4 scroll-mt-[120px]"
          >
            <h2 className="text-[18px] font-[700] text-[#111110] tracking-tight mt-[16px]">Fixes</h2>
            <div className="flex flex-col gap-5">
              {fixes.length === 0 && (
                <p className="text-[14px] text-[#A3A099]">No fixes generated yet.</p>
              )}
              {fixes.map((fix, i) => (
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.35, ease: "easeOut", delay: i * 0.05 }}
                  key={fix.id}
                  className="bg-[#FFFFFF] border border-[#E7E5E2] rounded-[14px] p-[24px] mb-[20px] flex flex-col gap-4"
                >
                  <h3 className="text-[16px] font-[700] text-[#111110]">{fix.title}</h3>
                  <p className="text-[14px] text-[#6F6B66] leading-relaxed max-w-[100ch]">
                    {fix.explanation}
                  </p>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-[16px] mt-2">
                    {/* Original Code */}
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center h-[24px]">
                        <span className="text-[11px] font-[700] text-[#A3A099] uppercase tracking-[0.04em]">Original Code</span>
                      </div>
                      <div className="relative">
                        <pre className="bg-[#FEF2F2] border border-[#FECACA] rounded-[10px] p-[16px] font-mono text-[13px] leading-relaxed text-red-900 overflow-auto h-[280px] shadow-inner custom-scrollbar">
                          <code>{fix.beforeCode}</code>
                        </pre>
                        <div className="absolute bottom-[1px] left-[1px] right-[1px] h-[8px] bg-gradient-to-t from-[#FEF2F2] to-transparent rounded-b-[9px] pointer-events-none" />
                      </div>
                    </div>

                    {/* Fixed Code */}
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center justify-between h-[24px]">
                        <span className="text-[11px] font-[700] text-[#A3A099] uppercase tracking-[0.04em]">Fixed Code</span>
                        <button
                          onClick={() => handleCopy(fix.id, fix.afterCode)}
                          className={cn(
                            "text-[12px] flex items-center gap-1.5 transition-colors",
                            copiedFixId === fix.id ? "text-[#16A34A]" : "text-[#6F6B66] hover:text-[#111110]"
                          )}
                        >
                          {copiedFixId === fix.id ? (
                            <>
                              <span>Copied</span>
                              <Check className="h-[12px] w-[12px]" />
                            </>
                          ) : (
                            <>
                              <Copy className="h-[12px] w-[12px]" />
                              <span>Copy</span>
                            </>
                          )}
                        </button>
                      </div>
                      <div className="relative">
                        <pre className="bg-[#F0FDF4] border border-[#BBF7D0] rounded-[10px] p-[16px] font-mono text-[13px] leading-relaxed text-green-900 overflow-auto h-[280px] shadow-inner custom-scrollbar">
                          <code>{fix.afterCode}</code>
                        </pre>
                        <div className="absolute bottom-[1px] left-[1px] right-[1px] h-[8px] bg-gradient-to-t from-[#F0FDF4] to-transparent rounded-b-[9px] pointer-events-none" />
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.section>

        </div>
      </div>
    </div>
  );
}
