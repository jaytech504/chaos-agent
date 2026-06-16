import Link from "next/link";
import Navbar from "@/components/navbar";
import Footer from "@/components/footer";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Shield,
  Zap,
  GitPullRequest,
  Search,
  BarChart3,
  Lock,
  ArrowRight,
} from "lucide-react";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-zinc-50/50">
      <Navbar variant="landing" />

      <main className="flex-1">
        {/* 1. Hero Section */}
        <section className="mx-auto max-w-7xl px-6 py-24 md:py-32 text-center animate-fade-in-up">
          <div className="mx-auto max-w-3xl flex flex-col items-center gap-6">
            <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-foreground">
              Ship reliable APIs. <br />
              <span className="bg-gradient-to-r from-primary to-blue-500 bg-clip-text text-transparent">
                Automatically.
              </span>
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground leading-relaxed max-w-2xl mt-4">
              PatchFlow analyzes your API endpoints, runs 18 reliability tests, identifies failures, and generates production-ready fixes — delivered as GitHub pull requests.
            </p>
            <div className="flex flex-col sm:flex-row items-center gap-4 mt-8">
              <Link
                href="/login"
                className={cn(buttonVariants({ size: "lg" }), "w-full sm:w-auto h-12 px-8")}
              >
                Get Started
              </Link>
              <Link
                href="#features"
                className={cn(buttonVariants({ variant: "outline", size: "lg" }), "w-full sm:w-auto h-12 px-8")}
              >
                View Demo
              </Link>
            </div>
          </div>
        </section>

        <Separator className="mx-auto max-w-7xl px-6" />

        {/* 2. Features Section */}
        <section id="features" className="mx-auto max-w-7xl px-6 py-24">
          <div className="text-center">
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              Everything you need for API reliability
            </h2>
            <p className="text-lg text-muted-foreground mt-4 max-w-2xl mx-auto">
              Comprehensive endpoint scanning, failure mode injection, and auto-generated fixes.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-16">
            {/* Feature 1 */}
            <div className="flex flex-col p-6 bg-white border border-border rounded-xl shadow-sm hover:shadow-md transition-shadow animate-fade-in animate-delay-100">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4 text-primary">
                <Shield className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold text-foreground">Failure Injection</h3>
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                18 failure modes across network, dependency, data, and resource categories to uncover hidden bugs.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="flex flex-col p-6 bg-white border border-border rounded-xl shadow-sm hover:shadow-md transition-shadow animate-fade-in animate-delay-200">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4 text-primary">
                <Zap className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold text-foreground">Instant Analysis</h3>
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                AI-powered root cause analysis with severity scoring, error classification, and failure pattern detection.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="flex flex-col p-6 bg-white border border-border rounded-xl shadow-sm hover:shadow-md transition-shadow animate-fade-in animate-delay-300">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4 text-primary">
                <GitPullRequest className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold text-foreground">Auto-Fix PRs</h3>
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                Production-ready code fixes delivered directly as GitHub pull requests, ready for review and merge.
              </p>
            </div>

            {/* Feature 4 */}
            <div className="flex flex-col p-6 bg-white border border-border rounded-xl shadow-sm hover:shadow-md transition-shadow animate-fade-in animate-delay-400">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4 text-primary">
                <Search className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold text-foreground">API Discovery</h3>
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                Automatic endpoint detection from OpenAPI specs, Postman collections, or target system manual entry.
              </p>
            </div>

            {/* Feature 5 */}
            <div className="flex flex-col p-6 bg-white border border-border rounded-xl shadow-sm hover:shadow-md transition-shadow animate-fade-in animate-delay-500">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4 text-primary">
                <BarChart3 className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold text-foreground">Risk Scoring</h3>
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                Comprehensive reliability score from 0 to 100 with an actionable, categorized breakdown of security gaps.
              </p>
            </div>

            {/* Feature 6 */}
            <div className="flex flex-col p-6 bg-white border border-border rounded-xl shadow-sm hover:shadow-md transition-shadow animate-fade-in">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4 text-primary">
                <Lock className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold text-foreground">Security First</h3>
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                Detects leaked stack traces, internal errors, exception dumps, and sensitive database detail exposure.
              </p>
            </div>
          </div>
        </section>

        <Separator className="mx-auto max-w-7xl px-6" />

        {/* 3. How It Works Section */}
        <section id="how-it-works" className="mx-auto max-w-7xl px-6 py-24">
          <div className="text-center">
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              How it works
            </h2>
            <p className="text-lg text-muted-foreground mt-4 max-w-2xl mx-auto">
              Three steps to reliable APIs
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-12 mt-16 relative">
            {/* Step 1 */}
            <div className="flex flex-col items-center text-center">
              <span className="text-sm font-semibold text-primary uppercase tracking-wide">Step 1</span>
              <h3 className="text-xl font-semibold text-foreground mt-2">Connect</h3>
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                Link your GitHub repository and provide your API endpoint URL or OpenAPI spec.
              </p>
            </div>

            {/* Step 2 */}
            <div className="flex flex-col items-center text-center">
              <span className="text-sm font-semibold text-primary uppercase tracking-wide">Step 2</span>
              <h3 className="text-xl font-semibold text-foreground mt-2">Analyze</h3>
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                PatchFlow injects 18 failure modes against every endpoint and observes how your API responds.
              </p>
            </div>

            {/* Step 3 */}
            <div className="flex flex-col items-center text-center">
              <span className="text-sm font-semibold text-primary uppercase tracking-wide">Step 3</span>
              <h3 className="text-xl font-semibold text-foreground mt-2">Fix</h3>
              <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                Review auto-generated pull requests with production-ready error handling for every gap found.
              </p>
            </div>
          </div>
        </section>

        <Separator className="mx-auto max-w-7xl px-6" />

        {/* 4. Reliability Testing Workflow Section */}
        <section className="mx-auto max-w-7xl px-6 py-24">
          <div className="text-center">
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              18 failure modes. Zero blind spots.
            </h2>
            <p className="text-lg text-muted-foreground mt-4 max-w-2xl mx-auto">
              We test across all major failure vectors to guarantee API resilience.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-16">
            {/* Network */}
            <div className="p-6 bg-white border border-border rounded-xl shadow-sm">
              <h3 className="text-lg font-semibold text-foreground mb-4">Network Failures</h3>
              <div className="flex flex-wrap gap-2">
                {["HTTP Timeout", "Connection Refused", "DNS Failure", "Slow Response", "Connection Reset"].map((mode) => (
                  <Badge key={mode} variant="secondary">
                    {mode}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Dependency */}
            <div className="p-6 bg-white border border-border rounded-xl shadow-sm">
              <h3 className="text-lg font-semibold text-foreground mb-4">Dependency Failures</h3>
              <div className="flex flex-wrap gap-2">
                {["HTTP 500", "Rate Limited (429)", "Service Unavailable", "Unauthorized", "Not Found"].map((mode) => (
                  <Badge key={mode} variant="secondary">
                    {mode}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Data */}
            <div className="p-6 bg-white border border-border rounded-xl shadow-sm">
              <h3 className="text-lg font-semibold text-foreground mb-4">Data Failures</h3>
              <div className="flex flex-wrap gap-2">
                {["Malformed JSON", "Empty Response", "Wrong Content-Type", "Partial Response", "Null Fields"].map((mode) => (
                  <Badge key={mode} variant="secondary">
                    {mode}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Resource */}
            <div className="p-6 bg-white border border-border rounded-xl shadow-sm">
              <h3 className="text-lg font-semibold text-foreground mb-4">Resource Failures</h3>
              <div className="flex flex-wrap gap-2">
                {["DB Connection Drop", "DB Timeout", "Constraint Violation"].map((mode) => (
                  <Badge key={mode} variant="secondary">
                    {mode}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* 5. GitHub Integration Section */}
        <section className="bg-zinc-50 border-y border-border py-24">
          <div className="mx-auto max-w-7xl px-6">
            <div className="text-center">
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
                Fixes that land in your codebase
              </h2>
              <p className="text-lg text-muted-foreground mt-4 max-w-2xl mx-auto">
                Every finding becomes a pull request. Review, approve, merge.
              </p>
            </div>

            <div className="mx-auto max-w-3xl mt-16 bg-white border border-border rounded-xl overflow-hidden shadow-md">
              <div className="border-b border-border bg-zinc-50 px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <GitPullRequest className="h-4 w-4 text-emerald-500" />
                  <span className="text-sm font-semibold text-foreground">fix: Add timeout handling for Stripe API calls #47</span>
                </div>
                <Badge className="bg-emerald-500 hover:bg-emerald-600">Open</Badge>
              </div>
              <div className="p-6 font-mono text-xs overflow-x-auto bg-zinc-900 text-zinc-100">
                <div className="text-zinc-400">// app/routes/payments.py</div>
                <div className="text-red-400">- response = httpx.post("https://api.stripe.com/v3/charges", json=payload)</div>
                <div className="text-green-400">+ try:</div>
                <div className="text-green-400">+     response = httpx.post("https://api.stripe.com/v3/charges", json=payload, timeout=5.0)</div>
                <div className="text-green-400">+ except httpx.TimeoutException:</div>
                <div className="text-green-400">+     raise HTTPException(status_code=504, detail="Payment gateway timeout")</div>
              </div>
            </div>
          </div>
        </section>

        {/* 6. CTA Section */}
        <section id="pricing" className="mx-auto max-w-7xl px-6 py-24 text-center">
          <div className="mx-auto max-w-3xl flex flex-col items-center gap-6">
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              Start shipping reliable APIs today
            </h2>
            <p className="text-lg text-muted-foreground max-w-xl mx-auto">
              Free to try. No credit card required. Connect your repo and run your first test in 2 minutes.
            </p>
            <Link
              href="/login"
              className={cn(buttonVariants({ size: "lg" }), "h-12 px-8 mt-4 group flex items-center gap-2")}
            >
              <span>Get Started with GitHub</span>
              <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
