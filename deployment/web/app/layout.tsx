import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { TerminalHeader } from "@/components/ui/terminal-header";
import { TopNavigation } from "@/components/ui/top-navigation";

export const metadata: Metadata = {
  title: "Sector Rotation Regime Discovery | NSE India Financial Terminal",
  description:
    "Production quantitative market regime discovery, dynamic sector rotation and portfolio execution telemetry for the Indian equity market.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className="dark">
      <head>
        {/* Anti-FOUC theme initialization script */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('sr_terminal_theme');if(t==='light'){document.documentElement.classList.remove('dark');}else{document.documentElement.classList.add('dark');}}catch(e){document.documentElement.classList.add('dark');}})();`,
          }}
        />
      </head>
      <body className="min-h-screen bg-terminal-bg text-terminal-primary antialiased flex flex-col selection:bg-terminal-primary selection:text-terminal-bg transition-colors duration-150 font-sans">
        <ThemeProvider>
          {/* Top Institutional Header & Persistent Navigation */}
          <TerminalHeader />
          <TopNavigation />

          {/* Primary Viewport Area */}
          <main className="flex-1 w-full max-w-[1600px] mx-auto px-3.5 sm:px-6 lg:px-8 py-4">
            {children}
          </main>

          {/* Institutional Terminal Footer */}
          <footer className="border-t border-terminal-border bg-terminal-panel/50 px-4 py-3 text-[11px] font-mono text-terminal-muted transition-colors">
            <div className="max-w-[1600px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-center sm:text-left">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span>
                  NSE Sector Rotation Architecture &bull; Causal HMM Gaussian Regime Ingestion
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span>EOD Catch-Up: 2026-11-06 Active</span>
                <span>&bull;</span>
                <span>Friction Model: 15 bps T+1</span>
                <span>&bull;</span>
                <span className="text-terminal-primary font-medium">Neon PostgreSQL Connected</span>
              </div>
            </div>
          </footer>
        </ThemeProvider>
      </body>
    </html>
  );
}
