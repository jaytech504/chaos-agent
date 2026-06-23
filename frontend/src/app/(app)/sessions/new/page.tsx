"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { 
  Play, 
  Loader2, 
  Search, 
  ArrowLeft, 
  Upload, 
  FileText, 
  Check, 
  Plus, 
  Trash,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Info
} from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";

interface Repo {
  name: string;
  full_name: string;
}

interface ManualEndpoint {
  path: string;
  method: string;
  description: string;
}

export default function NewSessionPage() {
  const router = useRouter();

  // Form states
  const [appName, setAppName] = useState("");
  const [appUrl, setAppUrl] = useState("");
  const [apiType, setApiType] = useState("openapi");
  const [openapiUrl, setOpenapiUrl] = useState("");
  const [selectedRepo, setSelectedRepo] = useState<Repo | null>(null);

  // File uploads
  const [specFile, setSpecFile] = useState<File | null>(null);
  const [collectionFile, setCollectionFile] = useState<File | null>(null);
  const [isDragOverSpec, setIsDragOverSpec] = useState(false);
  const [isDragOverCollection, setIsDragOverCollection] = useState(false);

  // Manual endpoints
  const [manualEndpoints, setManualEndpoints] = useState<ManualEndpoint[]>([]);
  const [newMethod, setNewMethod] = useState("GET");
  const [newPath, setNewPath] = useState("");

  // GitHub Repos loading/search states
  const [repos, setRepos] = useState<Repo[]>([]);
  const [reposLoading, setReposLoading] = useState(false);
  const [repoSearch, setRepoSearch] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Form validation/submit states
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New step/selection states
  const [step, setStep] = useState<"form" | "select">("form");
  const [previewData, setPreviewData] = useState<any | null>(null);
  const [selectedTempIds, setSelectedTempIds] = useState<Set<string>>(new Set());
  const [collapsedTags, setCollapsedTags] = useState<Set<string>>(new Set());
  const [hoveredTempId, setHoveredTempId] = useState<string | null>(null);

  // Fetch repos on mount
  useEffect(() => {
    const fetchRepos = async () => {
      const token = localStorage.getItem("patchflow_token");
      if (!token) return;

      setReposLoading(true);
      try {
        const response = await fetch("http://localhost:8000/api/auth/repos", {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (response.ok) {
          const data = await response.json();
          if (data && Array.isArray(data.repos)) {
            setRepos(data.repos);
          } else if (Array.isArray(data)) {
            setRepos(data);
          }
        }
      } catch (err) {
        console.warn("Could not fetch real repos, using mock fallback list.", err);
        setRepos([
          { name: "payments-api", full_name: "acme/payments-api" },
          { name: "user-service", full_name: "acme/user-service" },
          { name: "notification-api", full_name: "acme/notification-api" },
          { name: "inventory-api", full_name: "acme/inventory-api" },
          { name: "auth-service", full_name: "acme/auth-service" },
          { name: "analytics-api", full_name: "acme/analytics-api" },
        ]);
      } finally {
        setReposLoading(false);
      }
    };

    fetchRepos();
  }, []);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredRepos = repos.filter((r) =>
    r.full_name.toLowerCase().includes(repoSearch.toLowerCase())
  );

  const addManualEndpoint = () => {
    if (!newPath) return;
    const pathFormatted = newPath.startsWith("/") ? newPath : `/${newPath}`;
    setManualEndpoints((prev) => [
      ...prev,
      { method: newMethod, path: pathFormatted, description: `Manual entry: ${newMethod} ${pathFormatted}` },
    ]);
    setNewPath("");
  };

  const removeManualEndpoint = (index: number) => {
    setManualEndpoints((prev) => prev.filter((_, idx) => idx !== index));
  };

  // Preview API handler (Step 1 -> Step 2)
  const handlePreview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!appName || !appUrl) {
      setError("Please fill in the app name and URL.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    const token = localStorage.getItem("patchflow_token");
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    try {
      let response: Response;
      
      if (apiType === "openapi") {
        if (!openapiUrl) throw new Error("Please specify the OpenAPI spec URL.");
        response = await fetch("http://localhost:8000/api/discovery/preview/spec-url", {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({
            spec_url: openapiUrl,
          }),
        });
      } else if (apiType === "upload") {
        if (!specFile) throw new Error("Please select an OpenAPI file.");
        const formData = new FormData();
        formData.append("spec_file", specFile);

        response = await fetch("http://localhost:8000/api/discovery/preview/spec-file", {
          method: "POST",
          headers,
          body: formData,
        });
      } else if (apiType === "postman") {
        if (!collectionFile) throw new Error("Please select a Postman Collection file.");
        const formData = new FormData();
        formData.append("collection_file", collectionFile);

        response = await fetch("http://localhost:8000/api/discovery/preview/postman", {
          method: "POST",
          headers,
          body: formData,
        });
      } else {
        // Manual
        if (manualEndpoints.length === 0) throw new Error("Please add at least one endpoint.");
        response = await fetch("http://localhost:8000/api/discovery/preview/manual", {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({
            endpoints: manualEndpoints.map(ep => ({
              path: ep.path,
              method: ep.method,
              description: ep.description || "",
              payload: null
            })),
          }),
        });
      }

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to parse specification.");
      }

      const previewResult = await response.json();
      if (previewResult && previewResult.draft_id) {
        setPreviewData(previewResult);
        
        // Pre-select recommended endpoints by default
        const initialSelected = new Set<string>();
        if (previewResult.groups) {
          previewResult.groups.forEach((g: any) => {
            g.endpoints.forEach((ep: any) => {
              if (ep.recommended) {
                initialSelected.add(ep.temp_id);
              }
            });
          });
        }
        setSelectedTempIds(initialSelected);
        setStep("select");
      } else {
        throw new Error("No draft ID returned from preview backend.");
      }
    } catch (err: any) {
      console.warn("API request failed. Simulating preview in demo/offline mode.", err);
      // Demo Spec Preview Fallback
      const mockPreviewResult = {
        draft_id: "mock-draft-123",
        method: apiType,
        total_endpoints: apiType === "manual" ? manualEndpoints.length : 5,
        groups: [
          {
            tag: "auth",
            endpoints: [
              {
                temp_id: "post-api-auth-login",
                path: "/api/auth/login",
                method: "POST",
                description: "Login",
                sample_payload: { username: "admin", password: "password" },
                dependencies: ["database"],
                recommended: true,
                risk_note: null
              },
              {
                temp_id: "post-api-auth-logout",
                path: "/api/auth/logout",
                method: "POST",
                description: "Logout",
                sample_payload: null,
                dependencies: ["redis"],
                recommended: false,
                risk_note: "Admin/Session state modifications"
              }
            ]
          },
          {
            tag: "users",
            endpoints: [
              {
                temp_id: "get-api-users",
                path: "/api/users",
                method: "GET",
                description: "List users",
                sample_payload: null,
                dependencies: ["database"],
                recommended: true,
                risk_note: null
              },
              {
                temp_id: "delete-api-users-id",
                path: "/api/users/{id}",
                method: "DELETE",
                description: "Delete user",
                sample_payload: null,
                dependencies: ["database"],
                recommended: false,
                risk_note: "Destructive endpoint — deletes or removes resources"
              }
            ]
          }
        ]
      };
      
      if (apiType === "manual") {
        mockPreviewResult.groups = [
          {
            tag: "Manual",
            endpoints: manualEndpoints.map((ep, idx) => ({
              temp_id: `${ep.method.toLowerCase()}-${ep.path.replace(/[^a-z0-9_-]/gi, '-')}`,
              path: ep.path,
              method: ep.method,
              description: ep.description || `Manual Endpoint ${idx + 1}`,
              sample_payload: null,
              dependencies: ["database"],
              recommended: ep.method !== "DELETE",
              risk_note: ep.method === "DELETE" ? "Destructive endpoint — deletes or removes resources" : null
            }))
          }
        ];
      }
      
      setPreviewData(mockPreviewResult);
      const initialSelected = new Set<string>();
      mockPreviewResult.groups.forEach((g: any) => {
        g.endpoints.forEach((ep: any) => {
          if (ep.recommended) initialSelected.add(ep.temp_id);
        });
      });
      setSelectedTempIds(initialSelected);
      setStep("select");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Run Session API handler (Step 2 -> Start)
  const handleStartSession = async () => {
    if (selectedTempIds.size === 0) return;
    
    setIsSubmitting(true);
    setError(null);

    const token = localStorage.getItem("patchflow_token");
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    try {
      const response = await fetch("http://localhost:8000/api/sessions/start", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          draft_id: previewData?.draft_id,
          target_url: appUrl,
          target_name: appName,
          github_repo: selectedRepo?.full_name || null,
          selected_temp_ids: Array.from(selectedTempIds),
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to start session.");
      }

      const result = await response.json();
      if (result && result.session_id) {
        router.push(`/sessions/${result.session_id}`);
      } else {
        throw new Error("No session ID returned from backend.");
      }
    } catch (err: any) {
      console.warn("API start request failed. Simulating scan in demo/offline mode.", err);
      // Fallback redirection for testing/demo purposes
      setTimeout(() => {
        setIsSubmitting(false);
        router.push("/sessions/scan-3");
      }, 1500);
    }
  };

  return (
    <div className={cn("mx-auto px-6 py-12 w-full flex flex-col bg-white min-h-[calc(100vh-4rem)]", step === "form" ? "max-w-2xl" : "max-w-4xl")}>
      {step === "form" ? (
        <>
          {/* Back to Dashboard */}
          <div className="mb-6">
            <Link
              href="/dashboard"
              className="text-sm font-semibold text-primary hover:underline flex items-center gap-1.5 w-fit"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Back to Dashboard</span>
            </Link>
          </div>

          <div className="mb-8">
            <h1 className="text-3xl font-bold tracking-tight text-zinc-900">Run New Test</h1>
            <p className="text-sm text-zinc-500 mt-1">
              Configure endpoint failure injection scans against your API target.
            </p>
          </div>

          <form onSubmit={handlePreview} className="flex flex-col gap-6">
            {error && (
              <div className="p-3 text-xs font-semibold text-destructive bg-destructive/10 border border-destructive/20 rounded-lg">
                {error}
              </div>
            )}

            {/* App Name */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-semibold text-zinc-800" htmlFor="app-name">
                App Name
              </label>
              <input
                id="app-name"
                type="text"
                required
                placeholder="e.g. billing-gateway"
                value={appName}
                onChange={(e) => setAppName(e.target.value)}
                className="w-full px-4 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-zinc-400"
              />
            </div>

            {/* App URL */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-semibold text-zinc-800" htmlFor="app-url">
                App URL
              </label>
              <input
                id="app-url"
                type="url"
                required
                placeholder="e.g. https://api.acme.com/v1"
                value={appUrl}
                onChange={(e) => setAppUrl(e.target.value)}
                className="w-full px-4 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-zinc-400"
              />
            </div>

            {/* API Provision Tabs */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-semibold text-zinc-800">
                How to provide your API
              </label>
              <Tabs defaultValue="openapi" onValueChange={setApiType} className="w-full">
                <TabsList className="grid w-full grid-cols-4 bg-zinc-50 border border-zinc-200 p-1 rounded-lg">
                  <TabsTrigger value="openapi" className="text-xs py-1.5 font-medium rounded-md">OpenAPI URL</TabsTrigger>
                  <TabsTrigger value="upload" className="text-xs py-1.5 font-medium rounded-md">Upload file</TabsTrigger>
                  <TabsTrigger value="postman" className="text-xs py-1.5 font-medium rounded-md">Postman</TabsTrigger>
                  <TabsTrigger value="manual" className="text-xs py-1.5 font-medium rounded-md">Manual</TabsTrigger>
                </TabsList>

                <TabsContent value="openapi" className="mt-3">
                  <input
                    type="url"
                    placeholder="https://api.acme.com/openapi.json"
                    value={openapiUrl}
                    onChange={(e) => setOpenapiUrl(e.target.value)}
                    className="w-full px-4 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-zinc-400"
                  />
                </TabsContent>

                <TabsContent value="upload" className="mt-3">
                  {specFile ? (
                    <div className="border border-zinc-200 rounded-lg p-4 flex items-center justify-between bg-zinc-50">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="p-2 bg-primary/10 rounded-lg text-primary shrink-0">
                          <FileText className="h-5 w-5" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-zinc-900 truncate">
                            {specFile.name}
                          </p>
                          <p className="text-xs text-zinc-500">
                            {(specFile.size / 1024).toFixed(1)} KB
                          </p>
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setSpecFile(null)}
                        className="text-zinc-400 hover:text-red-500 hover:bg-red-50 p-2 h-auto"
                      >
                        <Trash className="h-4 w-4" />
                      </Button>
                    </div>
                  ) : (
                    <div
                      onDragOver={(e) => {
                        e.preventDefault();
                        setIsDragOverSpec(true);
                      }}
                      onDragLeave={(e) => {
                        e.preventDefault();
                        setIsDragOverSpec(false);
                      }}
                      onDrop={(e) => {
                        e.preventDefault();
                        setIsDragOverSpec(false);
                        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                          setSpecFile(e.dataTransfer.files[0]);
                        }
                      }}
                      className={cn(
                        "relative border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-200 min-h-[140px]",
                        isDragOverSpec 
                          ? "border-primary bg-primary/5 scale-[0.99]" 
                          : "border-zinc-200 bg-zinc-50/50 hover:border-zinc-300"
                      )}
                    >
                      <Upload className={cn("h-6 w-6 mb-2 transition-colors", isDragOverSpec ? "text-primary" : "text-zinc-400")} />
                      <span className="text-xs font-semibold text-zinc-700">
                        Drag & drop your OpenAPI JSON/YAML
                      </span>
                      <span className="text-[10px] text-zinc-400 mt-1">or click to browse local files</span>
                      <input
                        type="file"
                        accept=".json,.yaml,.yml"
                        onChange={(e) => {
                          if (e.target.files && e.target.files[0]) setSpecFile(e.target.files[0]);
                        }}
                        className="absolute inset-0 opacity-0 cursor-pointer"
                      />
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="postman" className="mt-3">
                  {collectionFile ? (
                    <div className="border border-zinc-200 rounded-lg p-4 flex items-center justify-between bg-zinc-50">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="p-2 bg-primary/10 rounded-lg text-primary shrink-0">
                          <FileText className="h-5 w-5" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-zinc-900 truncate">
                            {collectionFile.name}
                          </p>
                          <p className="text-xs text-zinc-500">
                            {(collectionFile.size / 1024).toFixed(1)} KB
                          </p>
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setCollectionFile(null)}
                        className="text-zinc-400 hover:text-red-500 hover:bg-red-50 p-2 h-auto"
                      >
                        <Trash className="h-4 w-4" />
                      </Button>
                    </div>
                  ) : (
                    <div
                      onDragOver={(e) => {
                        e.preventDefault();
                        setIsDragOverCollection(true);
                      }}
                      onDragLeave={(e) => {
                        e.preventDefault();
                        setIsDragOverCollection(false);
                      }}
                      onDrop={(e) => {
                        e.preventDefault();
                        setIsDragOverCollection(false);
                        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                          setCollectionFile(e.dataTransfer.files[0]);
                        }
                      }}
                      className={cn(
                        "relative border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-200 min-h-[140px]",
                        isDragOverCollection 
                          ? "border-primary bg-primary/5 scale-[0.99]" 
                          : "border-zinc-200 bg-zinc-50/50 hover:border-zinc-300"
                      )}
                    >
                      <FileText className={cn("h-6 w-6 mb-2 transition-colors", isDragOverCollection ? "text-primary" : "text-zinc-400")} />
                      <span className="text-xs font-semibold text-zinc-700">
                        Upload Postman Collection JSON
                      </span>
                      <span className="text-[10px] text-zinc-400 mt-1">v2.1 collection format supported</span>
                      <input
                        type="file"
                        accept=".json"
                        onChange={(e) => {
                          if (e.target.files && e.target.files[0]) setCollectionFile(e.target.files[0]);
                        }}
                        className="absolute inset-0 opacity-0 cursor-pointer"
                      />
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="manual" className="mt-3 flex flex-col gap-4">
                  <div className="flex gap-2">
                    <select
                      value={newMethod}
                      onChange={(e) => setNewMethod(e.target.value)}
                      className="px-3 py-2 border border-zinc-200 rounded-lg text-sm bg-white focus:outline-none"
                    >
                      <option>GET</option>
                      <option>POST</option>
                      <option>PUT</option>
                      <option>DELETE</option>
                    </select>
                    <input
                      type="text"
                      placeholder="e.g. /users"
                      value={newPath}
                      onChange={(e) => setNewPath(e.target.value)}
                      className="flex-1 px-4 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-zinc-400"
                    />
                    <Button type="button" onClick={addManualEndpoint} variant="outline" size="sm">
                      <Plus className="h-4 w-4 mr-1" /> Add
                    </Button>
                  </div>

                  {/* Added Endpoints List */}
                  {manualEndpoints.length > 0 && (
                    <div className="border border-zinc-200 rounded-lg divide-y divide-zinc-100 max-h-48 overflow-y-auto">
                      {manualEndpoints.map((ep, idx) => (
                        <div key={idx} className="p-3 flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2">
                            <span className={cn(
                              "font-bold px-1.5 py-0.5 rounded text-[10px]",
                              ep.method === "GET" ? "bg-blue-50 text-blue-700" :
                              ep.method === "POST" ? "bg-emerald-50 text-emerald-700" :
                              ep.method === "PUT" ? "bg-amber-50 text-amber-700" : "bg-red-50 text-red-700"
                            )}>
                              {ep.method}
                            </span>
                            <span className="font-mono text-zinc-700">{ep.path}</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => removeManualEndpoint(idx)}
                            className="text-zinc-400 hover:text-red-500 transition-colors"
                          >
                            <Trash className="h-4 w-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </div>

            {/* GitHub Repo Selector */}
            <div className="flex flex-col gap-2" ref={dropdownRef}>
              <label className="text-sm font-semibold text-zinc-800">
                GitHub Repo <span className="text-xs font-normal text-zinc-400">(Optional)</span>
              </label>

              <div className="relative">
                {reposLoading ? (
                  <div className="w-full flex items-center justify-between px-4 py-2 border border-zinc-200 rounded-lg bg-zinc-50/50 text-zinc-400 text-sm">
                    <span className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-zinc-400" />
                      Loading repositories...
                    </span>
                  </div>
                ) : (
                  <div>
                    <div
                      onClick={() => setDropdownOpen(!dropdownOpen)}
                      className="w-full px-4 py-2 border border-zinc-200 rounded-lg text-sm cursor-pointer flex justify-between items-center hover:border-zinc-300 transition-colors bg-white select-none"
                    >
                      <span className={cn(selectedRepo ? "text-zinc-900 font-medium" : "text-zinc-400")}>
                        {selectedRepo ? selectedRepo.full_name : "Select a repository to push fixes to"}
                      </span>
                      {selectedRepo && (
                        <span
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedRepo(null);
                          }}
                          className="text-xs text-zinc-400 hover:text-zinc-600 px-1.5 py-0.5 rounded hover:bg-zinc-100 transition-colors"
                        >
                          Clear
                        </span>
                      )}
                    </div>

                    {dropdownOpen && (
                      <div className="absolute z-10 w-full mt-1 bg-white border border-zinc-200 rounded-lg shadow-md max-h-60 overflow-hidden flex flex-col">
                        <div className="p-2 border-b border-zinc-100 flex items-center gap-2 bg-zinc-50/50">
                          <Search className="h-4 w-4 text-zinc-400 shrink-0" />
                          <input
                            type="text"
                            placeholder="Search repos..."
                            value={repoSearch}
                            onChange={(e) => setRepoSearch(e.target.value)}
                            className="w-full bg-transparent border-none focus:outline-none text-xs text-zinc-850"
                          />
                        </div>

                        <div className="overflow-y-auto max-h-48 divide-y divide-zinc-50">
                          {filteredRepos.length === 0 ? (
                            <div className="p-3 text-xs text-zinc-400 text-center">
                              No repositories found.
                            </div>
                          ) : (
                            filteredRepos.map((repo) => {
                              const isSelected = selectedRepo?.full_name === repo.full_name;
                              return (
                                <div
                                  key={repo.full_name}
                                  onClick={() => {
                                    setSelectedRepo(repo);
                                    setDropdownOpen(false);
                                    setRepoSearch("");
                                  }}
                                  className={cn(
                                    "p-3 text-xs cursor-pointer flex items-center justify-between hover:bg-zinc-50 transition-colors",
                                    isSelected && "bg-primary/5 text-primary font-semibold"
                                  )}
                                >
                                  <span>{repo.full_name}</span>
                                  {isSelected && <Check className="h-3.5 w-3.5" />}
                                </div>
                              );
                            })
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <span className="text-[10px] text-zinc-400">
                Skip repository connection if you do not want automated Pull Requests.
              </span>
            </div>

            {/* Submit */}
            <div className="mt-4 pt-6 border-t border-zinc-100 flex justify-end">
              <Button
                type="submit"
                disabled={isSubmitting || !appName || !appUrl}
                className="px-8 h-11 text-sm font-semibold flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white border-0"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Parsing API spec...</span>
                  </>
                ) : (
                  <>
                    <span>Preview Endpoints</span>
                    <Play className="h-4 w-4 fill-current ml-1" />
                  </>
                )}
              </Button>
            </div>
          </form>
        </>
      ) : (
        /* RENDER SELECT STEP */
        (() => {
          const totalEndpoints = previewData?.total_endpoints || 0;
          const groups = previewData?.groups || [];
          const selectedCount = selectedTempIds.size;

          const handleSelectAllRecommended = () => {
            const recommended = new Set<string>();
            groups.forEach((g: any) => {
              g.endpoints.forEach((ep: any) => {
                if (ep.recommended) recommended.add(ep.temp_id);
              });
            });
            setSelectedTempIds(recommended);
          };

          const handleSelectAll = () => {
            const all = new Set<string>();
            groups.forEach((g: any) => {
              g.endpoints.forEach((ep: any) => {
                all.add(ep.temp_id);
              });
            });
            setSelectedTempIds(all);
          };

          const handleDeselectAll = () => {
            setSelectedTempIds(new Set());
          };

          const toggleTempId = (tempId: string) => {
            setSelectedTempIds((prev) => {
              const next = new Set(prev);
              if (next.has(tempId)) {
                next.delete(tempId);
              } else {
                next.add(tempId);
              }
              return next;
            });
          };

          const toggleCollapsedTag = (tag: string) => {
            setCollapsedTags((prev) => {
              const next = new Set(prev);
              if (next.has(tag)) {
                next.delete(tag);
              } else {
                next.add(tag);
              }
              return next;
            });
          };

          return (
            <div className="w-full flex flex-col">
              {/* Back Button */}
              <div className="mb-6">
                <button
                  type="button"
                  onClick={() => setStep("form")}
                  className="text-sm font-semibold text-zinc-500 hover:text-zinc-800 flex items-center gap-1.5 w-fit bg-transparent border-0 cursor-pointer"
                >
                  <ArrowLeft className="h-4 w-4" />
                  <span>Back to Settings</span>
                </button>
              </div>

              <div className="mb-8">
                <h1 className="text-3xl font-bold tracking-tight text-zinc-900">Select Endpoints to Test</h1>
                <p className="text-sm text-zinc-500 mt-1">
                  {totalEndpoints} endpoints found. Review and select what to chaos test.
                </p>
              </div>

              {error && (
                <div className="mb-6 p-3 text-xs font-semibold text-destructive bg-destructive/10 border border-destructive/20 rounded-lg">
                  {error}
                </div>
              )}

              {groups.length === 0 ? (
                <div className="border border-zinc-200 rounded-xl p-12 text-center bg-zinc-50/50">
                  <Info className="h-8 w-8 text-zinc-400 mx-auto mb-3" />
                  <h3 className="text-sm font-bold text-zinc-950">No endpoints found</h3>
                  <p className="text-xs text-zinc-500 mt-1 mb-4">Go back and check your API source.</p>
                  <Button onClick={() => setStep("form")} variant="outline" size="sm">
                    Go Back
                  </Button>
                </div>
              ) : (
                <div className="flex flex-col gap-6 pb-24">
                  {/* Bulk Actions Bar */}
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 bg-zinc-50 border border-zinc-200 rounded-xl">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={handleSelectAllRecommended}
                        className="px-3 py-1.5 text-xs font-semibold bg-white border border-zinc-200 hover:border-zinc-350 hover:bg-zinc-50 text-zinc-650 hover:text-zinc-900 rounded-lg transition-all cursor-pointer"
                      >
                        Select All Recommended
                      </button>
                      <button
                        type="button"
                        onClick={handleSelectAll}
                        className="px-3 py-1.5 text-xs font-semibold bg-white border border-zinc-200 hover:border-zinc-350 hover:bg-zinc-50 text-zinc-650 hover:text-zinc-900 rounded-lg transition-all cursor-pointer"
                      >
                        Select All
                      </button>
                      <button
                        type="button"
                        onClick={handleDeselectAll}
                        className="px-3 py-1.5 text-xs font-semibold bg-white border border-zinc-200 hover:border-zinc-350 hover:bg-zinc-50 text-zinc-650 hover:text-zinc-900 rounded-lg transition-all cursor-pointer"
                      >
                        Deselect All
                      </button>
                    </div>
                    <span className="text-xs font-semibold text-zinc-500 pr-1 select-none">
                      {selectedCount} of {totalEndpoints} selected
                    </span>
                  </div>

                  {/* Groups */}
                  <div className="flex flex-col gap-4">
                    {groups.map((group: any) => {
                      const tag = group.tag;
                      const endpoints = group.endpoints || [];
                      const isCollapsed = collapsedTags.has(tag);
                      
                      const groupSelectedCount = endpoints.filter((ep: any) => selectedTempIds.has(ep.temp_id)).length;
                      const groupTotalCount = endpoints.length;
                      const isEntireGroupHighRisk = endpoints.every((ep: any) => !ep.recommended);

                      return (
                        <div key={tag} className="border border-zinc-200 rounded-xl overflow-hidden shadow-sm bg-white">
                          {/* Group Header */}
                          <div
                            onClick={() => toggleCollapsedTag(tag)}
                            className="px-4 py-3 bg-zinc-50/50 hover:bg-zinc-50 border-b border-zinc-200 flex items-center justify-between cursor-pointer select-none transition-colors"
                          >
                            <div className="flex items-center gap-2">
                              {isCollapsed ? (
                                <ChevronRight className="h-4 w-4 text-zinc-400" />
                              ) : (
                                <ChevronDown className="h-4 w-4 text-zinc-400" />
                              )}
                              <span className="text-sm font-bold text-zinc-900">{tag}</span>
                            </div>
                            <span className="text-xs text-zinc-500 font-medium select-none">
                              {groupSelectedCount} of {groupTotalCount} selected
                            </span>
                          </div>

                          {/* Group Content */}
                          {!isCollapsed && (
                            <div className="flex flex-col divide-y divide-zinc-100">
                              {isEntireGroupHighRisk && (
                                <div className="px-4 py-2 bg-amber-50/60 border-b border-amber-100 flex items-center gap-2 text-xs text-amber-800 select-none">
                                  <AlertTriangle className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                                  <span className="font-medium">This entire group is high-risk. Select with caution.</span>
                                </div>
                              )}

                              {endpoints.map((ep: any) => {
                                const isChecked = selectedTempIds.has(ep.temp_id);
                                const isHovered = hoveredTempId === ep.temp_id;
                                const isDangerous = !ep.recommended;

                                let methodClass = "";
                                switch (ep.method) {
                                  case "GET":
                                    methodClass = "bg-blue-50 text-blue-700 border border-blue-200/50";
                                    break;
                                  case "POST":
                                    methodClass = "bg-emerald-50 text-emerald-700 border border-emerald-200/50";
                                    break;
                                  case "PUT":
                                    methodClass = "bg-amber-50 text-amber-700 border border-amber-200/50";
                                    break;
                                  case "PATCH":
                                    methodClass = "bg-purple-50 text-purple-700 border border-purple-200/50";
                                    break;
                                  case "DELETE":
                                    methodClass = "bg-red-50 text-red-700 border border-red-200/50";
                                    break;
                                  default:
                                    methodClass = "bg-zinc-50 text-zinc-700 border border-zinc-200/50";
                                }

                                return (
                                  <div
                                    key={ep.temp_id}
                                    onMouseEnter={() => setHoveredTempId(ep.temp_id)}
                                    onMouseLeave={() => setHoveredTempId(null)}
                                    onClick={() => toggleTempId(ep.temp_id)}
                                    className={cn(
                                      "flex flex-col cursor-pointer transition-colors duration-150 select-none",
                                      isDangerous ? "bg-red-50/10 hover:bg-red-50/20" : "hover:bg-zinc-50/50"
                                    )}
                                  >
                                    <div className="flex items-center gap-3 px-4 py-3 min-w-0">
                                      <div className="flex items-center justify-center shrink-0">
                                        <input
                                          type="checkbox"
                                          checked={isChecked}
                                          onChange={() => {}}
                                          className="h-4 w-4 accent-red-600 rounded border-zinc-300 focus:ring-red-500 cursor-pointer"
                                        />
                                      </div>

                                      <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded shrink-0", methodClass)}>
                                        {ep.method}
                                      </span>

                                      <span className="font-mono text-[13px] text-zinc-700 font-medium truncate flex-1">
                                        {ep.path}
                                      </span>

                                      <span className="text-[13px] text-zinc-500 truncate max-w-[200px] text-right hidden sm:inline">
                                        {ep.description}
                                      </span>
                                    </div>

                                    {isDangerous && ep.risk_note && (
                                      <div className="pl-12 pr-4 pb-2.5 flex items-start gap-1.5 text-xs text-amber-700">
                                        <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
                                        <span>{ep.risk_note}</span>
                                      </div>
                                    )}

                                    {isHovered && ep.sample_payload && (
                                      <div className="pl-12 pr-4 pb-3 border-t border-dashed border-zinc-150/50 bg-zinc-50/30">
                                        <div className="mt-2 text-[10px] font-mono text-zinc-650">
                                          <p className="font-semibold text-[9px] text-zinc-400 mb-1 select-none">SAMPLE PAYLOAD</p>
                                          <pre className="p-2.5 bg-slate-50 border border-zinc-200 rounded-lg overflow-x-auto max-h-40 max-w-full">
                                            {JSON.stringify(ep.sample_payload, null, 2)}
                                          </pre>
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Sticky Footer Bar */}
              <div className="fixed bottom-0 left-0 right-0 border-t border-zinc-200 bg-white/95 backdrop-blur-sm py-4 px-6 z-20 flex justify-center shadow-[0_-4px_12px_rgba(0,0,0,0.03)]">
                <div className="max-w-4xl w-full flex items-center justify-between gap-4">
                  <button
                    type="button"
                    onClick={() => setStep("form")}
                    className="px-4 py-2 border border-zinc-200 text-zinc-700 font-semibold rounded-lg text-sm hover:bg-zinc-50 transition-colors cursor-pointer"
                  >
                    Back
                  </button>
                  
                  <span className="text-xs sm:text-sm font-semibold text-zinc-800 select-none">
                    {selectedCount} endpoints selected
                  </span>

                  <button
                    type="button"
                    disabled={isSubmitting || selectedCount === 0}
                    onClick={handleStartSession}
                    className={cn(
                      "px-8 h-10 text-sm font-semibold rounded-lg text-white transition-all flex items-center gap-2",
                      selectedCount === 0 
                        ? "bg-zinc-200 text-zinc-400 cursor-not-allowed"
                        : "bg-red-600 hover:bg-red-700 shadow-sm shadow-red-600/10 cursor-pointer"
                    )}
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Starting Run...</span>
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4 fill-current" />
                        <span>Run Chaos</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          );
        })()
      )}
    </div>
  );
}
