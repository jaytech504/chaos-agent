"use client";

import Link from "next/link";
import { Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGitHubLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("http://localhost:8000/api/auth/github/login");
      if (!response.ok) {
        throw new Error("Failed to get login URL from backend");
      }
      const data = await response.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        throw new Error("Backend did not return redirect URL");
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || "An unexpected error occurred");
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50/50 px-4">
      <div className="w-full max-w-md bg-white rounded-xl border border-border p-8 shadow-sm flex flex-col items-center text-center">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 font-bold text-foreground text-2xl mb-8">
          <Activity className="h-6 w-6 text-primary" />
          <span>PatchFlow</span>
        </Link>

        <h1 className="text-2xl font-bold tracking-tight text-foreground">Welcome back</h1>
        <p className="text-sm text-muted-foreground mt-2 mb-8">
          Log in with your GitHub account to continue
        </p>

        {error && (
          <div className="w-full p-3 mb-6 text-xs text-destructive bg-destructive/10 rounded-lg text-left">
            Error: {error}
          </div>
        )}

        <button
          onClick={handleGitHubLogin}
          disabled={loading}
          className="flex w-full items-center justify-center gap-3 rounded-lg bg-[#24292e] text-white font-medium py-3 hover:bg-[#1a1e22] transition-colors disabled:opacity-50 cursor-pointer"
        >
          <svg className="h-5 w-5 fill-current" viewBox="0 0 16 16" version="1.1" aria-hidden="true">
            <path fillRule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
          </svg>
          <span>{loading ? "Redirecting..." : "Continue with GitHub"}</span>
        </button>

        <p className="text-xs text-muted-foreground mt-6 leading-relaxed">
          By continuing, you agree to our{" "}
          <Link href="#" className="underline hover:text-foreground">
            Terms of Service
          </Link>{" "}
          and{" "}
          <Link href="#" className="underline hover:text-foreground">
            Privacy Policy
          </Link>
          .
        </p>

        <div className="w-full border-t border-border my-6" />

        <Link href="/" className="text-sm font-medium text-primary hover:underline flex items-center gap-1">
          &larr; Back to home
        </Link>
      </div>
    </div>
  );
}
