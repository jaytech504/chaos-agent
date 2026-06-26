import Link from "next/link";
import Navbar from "@/components/navbar";
import Footer from "@/components/footer";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Shield,
  Zap,
  GitPullRequest,
  Search,
  BarChart3,
  Lock,
  ArrowRight,
  Terminal,
  Activity,
  CheckCircle2,
} from "lucide-react";
import { TerminalAnimation } from "@/components/terminal-animation";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-background font-sans">
      <Navbar variant="landing" />

      <main className="flex-1">
        {/* 1. Hero Section */}
        <section className="mx-auto max-w-7xl px-6 pt-10 pb-20 md:pt-16 md:pb-32 lg:pt-20 lg:pb-40 animate-fade-in-up">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div className="flex flex-col gap-8 max-w-2xl">
              <h1 className="text-5xl md:text-6xl lg:text-7xl font-extrabold tracking-tight text-foreground leading-[1.1]">
                Ship reliable APIs. <br />
                <span className="text-primary">Automatically.</span>
              </h1>
              <p className="text-lg md:text-xl text-text-secondary leading-relaxed font-medium">
                Analyze your API endpoints, inject failure modes, identify critical vulnerabilities, and generate production-ready fixes — delivered instantly as pull requests.
              </p>
              <div className="flex flex-col sm:flex-row items-center gap-4 mt-2">
                <Link
                  href="/login"
                  className={cn(buttonVariants({ size: "lg" }), "w-full sm:w-auto h-12 px-8 font-medium shadow-sm hover:shadow-md transition-shadow")}
                >
                  Start Scanning
                </Link>
                <Link
                  href="#features"
                  className={cn(buttonVariants({ variant: "outline", size: "lg" }), "w-full sm:w-auto h-12 px-8 font-medium bg-card border-border-strong text-foreground hover:bg-muted transition-colors")}
                >
                  Explore Platform
                </Link>
              </div>
            </div>
            
            <div className="w-full relative animate-fade-in animate-delay-200">
              <TerminalAnimation />
            </div>
          </div>
        </section>

        {/* Logo/Integration Cloud */}
        <section className="border-y border-border bg-muted py-12">
          <div className="mx-auto max-w-7xl px-6 flex flex-col items-center">
            <p className="text-sm font-medium text-text-secondary mb-8 uppercase tracking-wider">Integrates seamlessly with</p>
            <div className="flex flex-wrap justify-center gap-12 md:gap-24 opacity-60 grayscale hover:grayscale-0 transition-all duration-500">
              {/* Placeholder SVGs for logos */}
              <div className="flex items-center gap-2 font-bold text-xl text-foreground"><GitPullRequest /> GitHub</div>
              <div className="flex items-center gap-2 font-bold text-xl text-foreground"><Terminal /> CI/CD</div>
              <div className="flex items-center gap-2 font-bold text-xl text-foreground"><Activity /> OpenAPI</div>
            </div>
          </div>
        </section>

        {/* 2. Features Section */}
        <section id="features" className="mx-auto max-w-7xl px-6 py-32">
          <div className="max-w-3xl mb-20">
            <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight text-foreground mb-6">
              A comprehensive toolkit for API resilience.
            </h2>
            <p className="text-xl text-text-secondary font-medium">
              Everything you need to discover, test, analyze, and automatically fix your APIs before they break in production.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Feature 1 */}
            <div className="group flex flex-col p-8 bg-card border border-border hover:border-border-strong rounded-none transition-all duration-200 shadow-sm hover:shadow-md hover:-translate-y-1">
              <Shield className="h-6 w-6 text-primary mb-6" />
              <h3 className="text-xl font-bold text-foreground mb-3 tracking-tight">Failure Injection</h3>
              <p className="text-base text-text-secondary leading-relaxed font-medium">
                18 distinct failure modes across network, dependency, data, and resource categories to stress-test your system.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="group flex flex-col p-8 bg-card border border-border hover:border-border-strong rounded-none transition-all duration-200 shadow-sm hover:shadow-md hover:-translate-y-1">
              <Zap className="h-6 w-6 text-primary mb-6" />
              <h3 className="text-xl font-bold text-foreground mb-3 tracking-tight">Instant Analysis</h3>
              <p className="text-base text-text-secondary leading-relaxed font-medium">
                AI-powered root cause analysis with severity scoring, precise error classification, and failure pattern detection.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="group flex flex-col p-8 bg-card border border-border hover:border-border-strong rounded-none transition-all duration-200 shadow-sm hover:shadow-md hover:-translate-y-1">
              <GitPullRequest className="h-6 w-6 text-primary mb-6" />
              <h3 className="text-xl font-bold text-foreground mb-3 tracking-tight">Auto-Fix PRs</h3>
              <p className="text-base text-text-secondary leading-relaxed font-medium">
                Production-ready code fixes delivered directly as GitHub pull requests. Review, approve, and merge instantly.
              </p>
            </div>

            {/* Feature 4 */}
            <div className="group flex flex-col p-8 bg-card border border-border hover:border-border-strong rounded-none transition-all duration-200 shadow-sm hover:shadow-md hover:-translate-y-1">
              <Search className="h-6 w-6 text-primary mb-6" />
              <h3 className="text-xl font-bold text-foreground mb-3 tracking-tight">API Discovery</h3>
              <p className="text-base text-text-secondary leading-relaxed font-medium">
                Automatic endpoint detection from OpenAPI specifications, Postman collections, or targeted codebase scanning.
              </p>
            </div>

            {/* Feature 5 */}
            <div className="group flex flex-col p-8 bg-card border border-border hover:border-border-strong rounded-none transition-all duration-200 shadow-sm hover:shadow-md hover:-translate-y-1">
              <BarChart3 className="h-6 w-6 text-primary mb-6" />
              <h3 className="text-xl font-bold text-foreground mb-3 tracking-tight">Risk Scoring</h3>
              <p className="text-base text-text-secondary leading-relaxed font-medium">
                Holistic reliability score from 0 to 100 with an actionable, categorized breakdown of your security posture.
              </p>
            </div>

            {/* Feature 6 */}
            <div className="group flex flex-col p-8 bg-card border border-border hover:border-border-strong rounded-none transition-all duration-200 shadow-sm hover:shadow-md hover:-translate-y-1">
              <Lock className="h-6 w-6 text-primary mb-6" />
              <h3 className="text-xl font-bold text-foreground mb-3 tracking-tight">Security First</h3>
              <p className="text-base text-text-secondary leading-relaxed font-medium">
                Proactively detects leaked stack traces, internal state errors, exception dumps, and database credential exposure.
              </p>
            </div>
          </div>
        </section>

        {/* 3. How It Works Section */}
        <section id="how-it-works" className="border-t border-border bg-card py-32">
          <div className="mx-auto max-w-7xl px-6">
            <h2 className="text-4xl font-extrabold tracking-tight text-foreground mb-16 text-center">
              The Path to Reliability
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
              {/* Connecting line for desktop */}
              <div className="hidden md:block absolute top-8 left-[16%] right-[16%] h-[1px] bg-border-strong"></div>

              {/* Step 1 */}
              <div className="flex flex-col relative pt-4 md:pt-0">
                <div className="w-16 h-16 rounded-none bg-background border border-border-strong flex items-center justify-center text-xl font-bold text-primary mb-6 shadow-sm mx-auto md:mx-0 z-10 relative">
                  01
                </div>
                <h3 className="text-2xl font-bold text-foreground mb-3 text-center md:text-left tracking-tight">Connect Repository</h3>
                <p className="text-base text-text-secondary leading-relaxed font-medium text-center md:text-left">
                  Link your GitHub workspace and provide your API configuration. We handle the discovery phase automatically.
                </p>
              </div>

              {/* Step 2 */}
              <div className="flex flex-col relative pt-4 md:pt-0">
                <div className="w-16 h-16 rounded-none bg-background border border-border-strong flex items-center justify-center text-xl font-bold text-primary mb-6 shadow-sm mx-auto md:mx-0 z-10 relative">
                  02
                </div>
                <h3 className="text-2xl font-bold text-foreground mb-3 text-center md:text-left tracking-tight">Execute Chaos</h3>
                <p className="text-base text-text-secondary leading-relaxed font-medium text-center md:text-left">
                  PatchFlow aggressively injects simulated failures against endpoints, strictly monitoring latency and state transitions.
                </p>
              </div>

              {/* Step 3 */}
              <div className="flex flex-col relative pt-4 md:pt-0">
                <div className="w-16 h-16 rounded-none bg-background border border-border-strong flex items-center justify-center text-xl font-bold text-primary mb-6 shadow-sm mx-auto md:mx-0 z-10 relative">
                  03
                </div>
                <h3 className="text-2xl font-bold text-foreground mb-3 text-center md:text-left tracking-tight">Merge Patches</h3>
                <p className="text-base text-text-secondary leading-relaxed font-medium text-center md:text-left">
                  Review the auto-generated PRs containing optimized error handling. Merge them to instantly secure your application.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* 5. GitHub Integration Demo Section */}
        <section className="bg-foreground text-card py-32">
          <div className="mx-auto max-w-7xl px-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
              <div>
                <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-6 text-card">
                  Fixes that land directly in your codebase.
                </h2>
                <p className="text-xl text-text-secondary font-medium mb-8">
                  Stop writing boilerplate error handlers. PatchFlow identifies the vulnerability and provides the exact code to fix it.
                </p>
                <ul className="flex flex-col gap-4">
                  <li className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                    <span className="text-base font-medium text-card">Automated branch creation</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                    <span className="text-base font-medium text-card">Context-aware try/catch blocks</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                    <span className="text-base font-medium text-card">Ready-to-merge GitHub workflows</span>
                  </li>
                </ul>
              </div>

              {/* Code diff mock */}
              <div className="w-full border border-white/20 bg-[#111110] rounded-lg shadow-2xl overflow-hidden font-mono text-sm">
                <div className="flex items-center justify-between px-4 py-3 border-b border-white/20 bg-[#1A1A1A]">
                  <div className="flex items-center gap-2 text-[#FAFAF9]">
                    <GitPullRequest className="h-4 w-4 text-[#16A34A]" />
                    <span className="font-medium tracking-tight">fix: Handle Stripe timeout #47</span>
                  </div>
                  <Badge className="bg-[#16A34A] hover:bg-[#16A34A] text-white border-none rounded-none px-2 py-0.5 text-xs font-bold uppercase tracking-wider">Open</Badge>
                </div>
                <div className="p-6 bg-[#000000] text-[#FAFAF9] leading-loose overflow-x-auto">
                  <div className="text-[#6F6B66] mb-2">{"// app/routes/payments.py"}</div>
                  <div className="text-[#DC2626] bg-red-950/30 px-2 -mx-2">{"- response = httpx.post(\"https://api.stripe.com/v3/charges\", json=payload)"}</div>
                  <div className="text-[#16A34A] bg-green-950/30 px-2 -mx-2">{"+ try:"}</div>
                  <div className="text-[#16A34A] bg-green-950/30 px-2 -mx-2">{"+     response = httpx.post(\"https://api.stripe.com/v3/charges\", json=payload, timeout=5.0)"}</div>
                  <div className="text-[#16A34A] bg-green-950/30 px-2 -mx-2">{"+ except httpx.TimeoutException:"}</div>
                  <div className="text-[#16A34A] bg-green-950/30 px-2 -mx-2">{"+     raise HTTPException(status_code=504, detail=\"Payment gateway timeout\")"}</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 6. CTA Section */}
        <section className="mx-auto max-w-7xl px-6 py-32 text-center">
          <div className="mx-auto max-w-3xl flex flex-col items-center gap-8">
            <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight text-foreground">
              Ready to secure your API?
            </h2>
            <p className="text-xl text-text-secondary font-medium">
              Join leading developer teams using PatchFlow to automate their reliability engineering. Connect your repository and run a scan in seconds.
            </p>
            <Link
              href="/login"
              className={cn(buttonVariants({ size: "lg" }), "h-14 px-10 text-lg font-bold shadow-md hover:shadow-lg transition-all group flex items-center gap-2")}
            >
              <span>Get Started</span>
              <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
