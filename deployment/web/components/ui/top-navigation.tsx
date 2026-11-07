"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Compass,
  LineChart,
  ShieldAlert,
  Calendar,
  Zap,
  Cpu,
  BookOpen,
  Menu,
  X,
} from "lucide-react";

export interface NavItem {
  name: string;
  shortName: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const NAV_ITEMS: NavItem[] = [
  {
    name: "Home / Overview",
    shortName: "Overview",
    href: "/",
    icon: LayoutDashboard,
  },
  {
    name: "Sector Rotation Intelligence / RRG",
    shortName: "Sector RRG",
    href: "/sector-rotation",
    icon: Compass,
  },
  {
    name: "Portfolio Analytics",
    shortName: "Portfolios",
    href: "/portfolio-analytics",
    icon: LineChart,
  },
  {
    name: "Risk & Drawdown",
    shortName: "Risk & DD",
    href: "/risk-drawdown",
    icon: ShieldAlert,
  },
  {
    name: "Economic Calendar",
    shortName: "Calendar",
    href: "/economic-calendar",
    icon: Calendar,
  },
  {
    name: "Event Intelligence",
    shortName: "Event Shocks",
    href: "/event-intelligence",
    icon: Zap,
  },
  {
    name: "Regime Intelligence",
    shortName: "Regimes",
    href: "/regime-intelligence",
    icon: Cpu,
  },
  {
    name: "Research & Methodology",
    shortName: "Methodology",
    href: "/research-methodology",
    icon: BookOpen,
  },
];

export function TopNavigation() {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isActive = (href: string) => {
    if (href === "/") {
      return pathname === "/";
    }
    return pathname.startsWith(href);
  };

  return (
    <nav className="border-b border-terminal-border bg-terminal-panel/80 backdrop-blur-sm sticky top-0 z-40 transition-colors">
      <div className="max-w-[1600px] mx-auto px-4">
        {/* Desktop Navigation Bar */}
        <div className="flex items-center justify-between">
          <div className="hidden lg:flex items-center space-x-1 overflow-x-auto py-1">
            {NAV_ITEMS.map((item) => {
              const active = isActive(item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`inline-flex items-center gap-1.5 px-3 py-2 text-xs font-mono font-medium rounded-t-sm transition-colors whitespace-nowrap border-b-2 ${
                    active
                      ? "border-emerald-500 text-terminal-primary bg-terminal-secondary/60 font-semibold"
                      : "border-transparent text-terminal-muted hover:text-terminal-primary hover:bg-terminal-secondary/30"
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${active ? "text-emerald-500" : "text-terminal-muted"}`} />
                  <span>{item.shortName}</span>
                </Link>
              );
            })}
          </div>

          {/* Mobile Menu Toggle Button */}
          <div className="lg:hidden flex items-center justify-between w-full py-2">
            <span className="text-xs font-mono text-terminal-muted">
              Active: <strong className="text-terminal-primary">{NAV_ITEMS.find((i) => isActive(i.href))?.name || "Terminal"}</strong>
            </span>
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-1.5 rounded border border-terminal-border bg-terminal-secondary text-terminal-primary hover:bg-terminal-panel focus:outline-none"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Drawer */}
        {mobileMenuOpen && (
          <div className="lg:hidden border-t border-terminal-border py-2 space-y-1">
            {NAV_ITEMS.map((item) => {
              const active = isActive(item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-2.5 px-3 py-2 text-xs font-mono rounded transition-colors ${
                    active
                      ? "bg-terminal-secondary text-terminal-primary font-semibold border-l-2 border-emerald-500"
                      : "text-terminal-muted hover:text-terminal-primary hover:bg-terminal-secondary/40"
                  }`}
                >
                  <Icon className={`w-4 h-4 ${active ? "text-emerald-500" : "text-terminal-muted"}`} />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </nav>
  );
}

