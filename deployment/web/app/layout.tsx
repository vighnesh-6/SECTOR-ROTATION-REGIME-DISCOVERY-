import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { TerminalHeader } from "@/components/ui/terminal-header";
import { TopNavigation } from "@/components/ui/top-navigation";

export const metadata: Metadata = {
  title: "Sector Rotation Regime Discovery | NSE India Financial Terminal",
  description:
    "Quantitative market regime discovery, dynamic sector rotation and portfolio execution telemetry for the Indian equity market.",
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

          <footer className="border-t border-terminal-border bg-terminal-panel px-4 py-5 text-xs text-terminal-muted"><div className="max-w-[1600px] mx-auto flex flex-col sm:flex-row justify-between gap-2"><span>NSE India · Index-level quantitative research</span><span>Simulation results are not investment advice. Source dates and provenance are shown per view.</span></div></footer>
        </ThemeProvider>
      </body>
    </html>
  );
}
