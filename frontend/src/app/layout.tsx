import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PatchFlow — API Reliability Testing & Auto-Fix",
  description:
    "PatchFlow analyzes your APIs, performs reliability testing, identifies failures, traces root causes, and generates GitHub pull requests with production-ready fixes.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
