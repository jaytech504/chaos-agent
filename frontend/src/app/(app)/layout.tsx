"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Activity, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);
  const [user, setUser] = useState<{ github_username: string; github_avatar_url: string | null } | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("patchflow_token");
    if (!token) {
      router.push("/login");
      return;
    }

    try {
      const storedUser = localStorage.getItem("patchflow_user");
      if (storedUser) {
        setUser(JSON.parse(storedUser));
      }
    } catch (e) {
      console.error("Failed to parse user details from local storage", e);
    }

    setAuthorized(true);
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("patchflow_token");
    localStorage.removeItem("patchflow_user");
    router.push("/");
  };

  if (!authorized) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50/50">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="h-8 w-8 text-primary animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
          <h2 className="text-lg font-semibold text-foreground">Loading...</h2>
        </div>
      </div>
    );
  }

  const username = user?.github_username || "User";
  const initials = username.substring(0, 2).toUpperCase();

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50/20">
      {/* Top navbar */}
      <header className="sticky top-0 z-50 bg-white border-b border-border h-16 flex items-center px-6 justify-between">
        <div className="flex items-center gap-8">
          <Link href="/dashboard" className="flex items-center gap-2 font-semibold text-foreground">
            <Activity className="h-5 w-5 text-primary" />
            <span>PatchFlow</span>
          </Link>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Avatar className="h-8 w-8">
              {user?.github_avatar_url && (
                <AvatarImage src={user.github_avatar_url} alt={username} />
              )}
              <AvatarFallback>{initials}</AvatarFallback>
            </Avatar>
            <span className="text-sm font-medium text-muted-foreground hidden sm:inline">
              {username}
            </span>
          </div>

          <Button variant="ghost" size="icon" onClick={handleLogout} title="Log out">
            <LogOut className="h-4 w-4 text-muted-foreground hover:text-destructive transition-colors" />
          </Button>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 bg-zinc-50/30 flex flex-col">{children}</main>
    </div>
  );
}
