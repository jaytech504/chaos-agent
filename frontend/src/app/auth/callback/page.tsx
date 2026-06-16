"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import Link from "next/link";

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    if (!code) {
      setError("No authorization code found in the URL.");
      return;
    }

    const exchangeCode = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/auth/github/callback?code=${code}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || "Failed to authenticate with GitHub");
        }

        const data = await response.json();
        if (data.access_token) {
          localStorage.setItem("patchflow_token", data.access_token);
          // Store user details in localStorage
          localStorage.setItem("patchflow_user", JSON.stringify(data.user || {
            github_username: data.github_username || "User",
            github_avatar_url: data.github_avatar_url || null
          }));
          router.push("/dashboard");
        } else {
          throw new Error("No token returned from backend");
        }
      } catch (err: any) {
        console.error(err);
        setError(err.message || "An error occurred during authentication.");
      }
    };

    exchangeCode();
  }, [searchParams, router]);

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50/50 px-4">
        <div className="w-full max-w-md bg-white rounded-xl border border-border p-8 shadow-sm flex flex-col items-center text-center">
          <div className="h-12 w-12 rounded-full bg-destructive/10 text-destructive flex items-center justify-center mb-4">
            <span className="text-xl font-bold">!</span>
          </div>
          <h2 className="text-xl font-bold text-foreground">Authentication Failed</h2>
          <p className="text-sm text-muted-foreground mt-2 mb-6">
            {error}
          </p>
          <Link href="/login" className="text-sm font-semibold text-primary hover:underline">
            Go back to login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50/50">
      <div className="flex flex-col items-center gap-4 text-center">
        <Loader2 className="h-8 w-8 text-primary animate-spin" />
        <h2 className="text-lg font-semibold text-foreground">Authenticating...</h2>
        <p className="text-sm text-muted-foreground">Exchanging GitHub authorization code for session...</p>
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50/50">
        <div className="flex flex-col items-center gap-4 text-center">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
          <h2 className="text-lg font-semibold text-foreground">Loading authentication page...</h2>
        </div>
      </div>
    }>
      <CallbackHandler />
    </Suspense>
  );
}
