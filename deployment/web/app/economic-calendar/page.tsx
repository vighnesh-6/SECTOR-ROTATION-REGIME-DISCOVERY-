"use client";

import React, { useEffect, useState } from "react";
import { TerminalPanel } from "@/components/ui/terminal-panel";
import { MetricTile } from "@/components/ui/metric-tile";
import { StatusBadge } from "@/components/ui/status-badge";
import { SectionHeader } from "@/components/ui/section-header";
import { DataTable, ColumnDef } from "@/components/ui/data-table";
import { LoadingMetricSkeleton, LoadingTableSkeleton } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";
import { RefreshCw, Filter } from "lucide-react";

interface MacroEvent {
  event_id: number;
  date: string;
  category: string;
  title: string;
  severity: string;
  region: string;
  source: string;
}

export default function EconomicCalendarPage() {
  const [events, setEvents] = useState<MacroEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [error, setError] = useState<string | null>(null);

  const fetchEvents = async () => {
    try {
      setError(null);
      const res = await fetch("/api/v1/events?limit=150");
      if (!res.ok) throw new Error(`Events API error: HTTP ${res.status}`);
      const json = await res.json();
      setEvents(json.events || []);
    } catch (e: any) {
      console.error("Failed to load events:", e);
      setError(e.message || "Failed to load macro events.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, []);

  const getSeverityBadge = (severityStr: string) => {
    const isHigh = severityStr.toLowerCase().includes("high");
    const isMed = severityStr.toLowerCase().includes("medium");
    if (isHigh) return <StatusBadge label="HIGH SEVERITY" variant="danger" />;
    if (isMed) return <StatusBadge label="MEDIUM" variant="warning" />;
    return <StatusBadge label="LOW" variant="neutral" />;
  };

  const columns: ColumnDef<MacroEvent>[] = [
    {
      key: "date",
      header: "Session Date",
      width: "120px",
      render: (row) => (
        <span className="font-mono text-terminal-primary">{row.date}</span>
      ),
    },
    {
      key: "category",
      header: "Category",
      render: (row) => (
        <span className="px-2 py-0.5 rounded-sm bg-terminal-secondary text-[11px] font-mono border border-terminal-border text-terminal-primary">
          {row.category}
        </span>
      ),
    },
    {
      key: "title",
      header: "Macroeconomic Catalyst & Event",
      render: (row) => (
        <span className="text-terminal-primary font-medium">{row.title}</span>
      ),
    },
    {
      key: "region",
      header: "Jurisdiction",
      align: "center",
      render: (row) => {
        const cleanRegion = (row.region || "").replace("Region:", "").trim() || "India";
        return (
          <span className="font-mono text-[11px] text-terminal-muted">
            {cleanRegion}
          </span>
        );
      },
    },
    {
      key: "severity",
      header: "Impact Severity",
      align: "right",
      render: (row) => getSeverityBadge(row.severity || ""),
    },
  ];

  const filteredEvents = selectedCategory === "ALL"
    ? events
    : events.filter((e) => e.category.toLowerCase().includes(selectedCategory.toLowerCase()));

  const highSeverityCount = events.filter((e) =>
    (e.severity || "").toLowerCase().includes("high")
  ).length;

  const monetaryCount = events.filter((e) =>
    (e.category || "").toLowerCase().includes("monetary")
  ).length;

  const fiscalCount = events.filter((e) =>
    (e.category || "").toLowerCase().includes("budget") || (e.category || "").toLowerCase().includes("fiscal")
  ).length;

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Institutional Economic Calendar & Macro Shocks"
        description="Chronological Macro Catalysts &bull; RBI MPC Policy, Inflation Prints, Union Budgets & Global Fed Shocks"
        badge={
          <StatusBadge
            label={`${events.length} VERIFIED EVENTS`}
            variant="neutral"
          />
        }
        action={
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setRefreshing(true);
                fetchEvents();
              }}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded-sm border border-terminal-border bg-terminal-secondary hover:bg-terminal-border/40 text-terminal-primary transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
              <span>{refreshing ? "FETCHING" : "SYNC"}</span>
            </button>
          </div>
        }
      />

      {/* KPI Tiles computed dynamically */}
      {loading ? (
        <LoadingMetricSkeleton count={4} />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
          <MetricTile
            label="Total Macro Events"
            value={String(events.length)}
            delta="2019 through 2026"
            deltaType="neutral"
            subtitle="Curated Event Database"
          />
          <MetricTile
            label="High Severity Catalysts"
            value={String(highSeverityCount)}
            delta="Market-Moving Shocks"
            deltaType="negative"
            subtitle="Severity: High Classification"
          />
          <MetricTile
            label="Central Bank Actions"
            value={String(monetaryCount)}
            delta="RBI MPC & US Fed Decisions"
            deltaType="neutral"
            subtitle="Monetary Policy Category"
          />
          <MetricTile
            label="Fiscal & Budget Catalysts"
            value={String(fiscalCount)}
            delta="Union Budgets & Reforms"
            deltaType="neutral"
            subtitle="Fiscal Policy Category"
          />
        </div>
      )}

      {/* Filter Tabs & Event Table */}
      <TerminalPanel
        title="Chronological Macroeconomic Catalog (Neon Database)"
        subtitle="Historical catalog aligned with Gaussian HMM regime transitions"
        headerRight={
          <div className="flex items-center gap-1 bg-terminal-secondary/80 p-0.5 rounded-sm border border-terminal-border">
            {["ALL", "monetary", "summit", "trade", "budget"].map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-2 py-0.5 text-[10px] font-mono uppercase rounded-sm transition-colors ${
                  selectedCategory === cat
                    ? "bg-terminal-primary text-terminal-bg font-bold"
                    : "text-terminal-muted hover:text-terminal-primary"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        }
      >
        {loading ? (
          <LoadingTableSkeleton rows={8} columns={5} />
        ) : error ? (
          <EmptyState
            title="Macro Events Offline"
            description={error}
            action={
              <button
                onClick={fetchEvents}
                className="px-3 py-1.5 text-xs font-mono rounded-sm border border-terminal-border bg-terminal-panel text-terminal-primary"
              >
                Retry
              </button>
            }
          />
        ) : (
          <DataTable
            columns={columns}
            data={filteredEvents}
            keyField="event_id"
            zebra
          />
        )}
      </TerminalPanel>
    </div>
  );
}
