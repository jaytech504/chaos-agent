"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Play, Loader2, Search, ArrowLeft, Upload, FileText, Check, Plus, Trash } from "lucide-react";
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

  const handleSubmit = async (e: React.FormEvent) => {
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
        response = await fetch("http://localhost:8000/api/sessions/from-spec-url", {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({
            target_url: appUrl,
            spec_url: openapiUrl,
            target_name: appName,
            github_repo: selectedRepo?.full_name || null,
          }),
        });
      } else if (apiType === "upload") {
        if (!specFile) throw new Error("Please select an OpenAPI file.");
        const formData = new FormData();
        formData.append("target_url", appUrl);
        formData.append("target_name", appName);
        formData.append("spec_file", specFile);
        if (selectedRepo) formData.append("github_repo", selectedRepo.full_name);

        response = await fetch("http://localhost:8000/api/sessions/from-spec-file", {
          method: "POST",
          headers,
          body: formData,
        });
      } else if (apiType === "postman") {
        if (!collectionFile) throw new Error("Please select a Postman Collection file.");
        const formData = new FormData();
        formData.append("target_url", appUrl);
        formData.append("target_name", appName);
        formData.append("collection_file", collectionFile);
        if (selectedRepo) formData.append("github_repo", selectedRepo.full_name);

        response = await fetch("http://localhost:8000/api/sessions/from-postman", {
          method: "POST",
          headers,
          body: formData,
        });
      } else {
        // Manual
        if (manualEndpoints.length === 0) throw new Error("Please add at least one endpoint.");
        response = await fetch("http://localhost:8000/api/sessions/from-manual", {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({
            target_url: appUrl,
            target_name: appName,
            endpoints: manualEndpoints,
            github_repo: selectedRepo?.full_name || null,
          }),
        });
      }

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to create session on backend.");
      }

      const sessionResult = await response.json();
      if (sessionResult && sessionResult.session_id) {
        router.push(`/sessions/${sessionResult.session_id}`);
      } else {
        throw new Error("No session ID returned from backend.");
      }
    } catch (err: any) {
      console.warn("API request failed. Simulating session in demo/offline mode.", err);
      // Fallback redirection for testing/demo purposes
      setTimeout(() => {
        setIsSubmitting(false);
        router.push("/sessions/scan-3");
      }, 1500);
    }
  };

  return (
    <div className="mx-auto max-w-2xl px-6 py-12 w-full flex flex-col bg-white min-h-[calc(100vh-4rem)]">
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

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
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
            className="px-8 h-11 text-sm font-semibold flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Starting Run...</span>
              </>
            ) : (
              <>
                <Play className="h-4 w-4 fill-current" />
                <span>Run</span>
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
