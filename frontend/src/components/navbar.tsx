"use client";

import Link from "next/link";
import { Activity } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface NavbarProps {
  variant?: "landing" | "app";
}

export default function Navbar({ variant = "landing" }: NavbarProps) {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        {/* Left side: Logo */}
        <Link href={variant === "app" ? "/dashboard" : "/"} className="flex items-center gap-2 font-semibold text-foreground">
          <Activity className="h-5 w-5 text-primary" />
          <span>PatchFlow</span>
        </Link>

        {/* Center: Nav links (only for landing variant) */}
        {variant === "landing" && (
          <nav className="hidden md:flex items-center gap-6">
            <Link href="#features" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
              Features
            </Link>
            <Link href="#how-it-works" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
              How it works
            </Link>
            <Link href="#pricing" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
              Pricing
            </Link>
          </nav>
        )}

        {/* Right side: Action */}
        <div className="flex items-center gap-4">
          {variant === "landing" ? (
            <Link
              href="/login"
              className={cn(buttonVariants({ size: "sm" }))}
            >
              Login with GitHub
            </Link>
          ) : (
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-medium text-primary border border-primary/20">
                U
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

